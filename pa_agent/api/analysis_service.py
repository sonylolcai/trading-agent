"""Background analysis task management for the local Web API."""
from __future__ import annotations

import queue
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pa_agent.api.events import normalize_event, sse_message
from pa_agent.data.base import KlineFrame
from pa_agent.records.schema import AnalysisRecord
from pa_agent.util.threading import CancelToken, OrchestratorEvent

AnalysisStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "cancelling"]


class AnalysisRunner(Protocol):
    def __call__(
        self,
        frame: KlineFrame,
        cancel_token: CancelToken,
        emit: Callable[[dict[str, Any] | OrchestratorEvent], None],
    ) -> AnalysisRecord: ...


@dataclass
class AnalysisTask:
    analysis_id: str
    frame: KlineFrame
    cancel_token: CancelToken = field(default_factory=CancelToken)
    status: AnalysisStatus = "queued"
    events: list[dict[str, Any]] = field(default_factory=list)
    record: AnalysisRecord | None = None
    error: str | None = None
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    _queue: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    thread: threading.Thread | None = None

    def add_event(self, event: dict[str, Any] | OrchestratorEvent) -> dict[str, Any]:
        normalized = normalize_event(event)
        with self._lock:
            self.events.append(normalized)
            self.updated_at_ms = int(time.time() * 1000)
        self._queue.put(normalized)
        return normalized

    def set_status(self, status: AnalysisStatus) -> None:
        with self._lock:
            self.status = status
            self.updated_at_ms = int(time.time() * 1000)


class AnalysisTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, AnalysisTask] = {}
        self._lock = threading.Lock()

    def start(self, frame: KlineFrame, runner: AnalysisRunner) -> AnalysisTask:
        analysis_id = uuid.uuid4().hex
        task = AnalysisTask(analysis_id=analysis_id, frame=frame)
        with self._lock:
            self._tasks[analysis_id] = task

        thread = threading.Thread(
            target=self._run_task,
            args=(task, runner),
            name=f"pa-agent-analysis-{analysis_id[:8]}",
            daemon=True,
        )
        task.thread = thread
        task.set_status("running")
        thread.start()
        return task

    def get(self, analysis_id: str) -> AnalysisTask | None:
        with self._lock:
            return self._tasks.get(analysis_id)

    def cancel(self, analysis_id: str) -> AnalysisTask | None:
        task = self.get(analysis_id)
        if task is None:
            return None
        task.cancel_token.set()
        if task.status in {"queued", "running"}:
            task.set_status("cancelling")
            task.add_event({"type": "cancellation_requested"})
        return task

    def sse_events(self, analysis_id: str) -> Iterator[str]:
        task = self.get(analysis_id)
        if task is None:
            return

        index = 0
        while True:
            while index < len(task.events):
                event = task.events[index]
                index += 1
                yield sse_message(event)
            if task.status in {"succeeded", "failed", "cancelled"}:
                return
            try:
                task._queue.get(timeout=0.25)
            except queue.Empty:
                continue

    def _run_task(self, task: AnalysisTask, runner: AnalysisRunner) -> None:
        try:
            record = runner(task.frame, task.cancel_token, task.add_event)
            task.record = record
            if task.cancel_token.is_set():
                task.set_status("cancelled")
            elif record.exception and record.exception.get("type") == "user_cancelled":
                task.set_status("cancelled")
            elif record.exception:
                task.set_status("failed")
            else:
                task.set_status("succeeded")
        except Exception as exc:  # noqa: BLE001
            task.error = str(exc)
            task.set_status("cancelled" if task.cancel_token.is_set() else "failed")
            task.add_event({"type": "error", "message": str(exc)})
        finally:
            task.add_event(
                {
                    "type": "task_finished",
                    "status": "cancelled" if task.cancel_token.is_set() else task.status,
                }
            )


def default_analysis_runner(
    frame: KlineFrame,
    cancel_token: CancelToken,
    emit: Callable[[dict[str, Any] | OrchestratorEvent], None],
) -> AnalysisRecord:
    """Run the production two-stage orchestrator in the background thread."""
    from pa_agent.app_context import AppContext
    from pa_agent.orchestrator.two_stage import TwoStageOrchestrator

    ctx = AppContext.bootstrap()
    orchestrator = TwoStageOrchestrator(
        client=ctx.client,
        assembler=ctx.assembler,
        router=ctx.router,
        validator=ctx.validator,
        pending_writer=ctx.pending_writer,
        exp_reader=ctx.exp_reader,
        settings=ctx.settings,
    )
    return orchestrator.submit(
        frame,
        cancel_token,
        emit,
        on_stage1_reasoning=lambda text: emit(
            {"type": "reasoning_delta", "stage": "stage1", "text": text}
        ),
        on_stage1_content=lambda text: emit(
            {"type": "content_delta", "stage": "stage1", "text": text}
        ),
        on_stage2_reasoning=lambda text: emit(
            {"type": "reasoning_delta", "stage": "stage2", "text": text}
        ),
        on_stage2_content=lambda text: emit(
            {"type": "content_delta", "stage": "stage2", "text": text}
        ),
        on_stage_prompt=lambda stage, system, user: emit(
            {
                "type": "stage_prompt",
                "stage": stage,
                "system": system,
                "user": user,
            }
        ),
        on_stage2_files=lambda files: emit({"type": "stage2_files", "files": files}),
    )
