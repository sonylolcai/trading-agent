"""Background analysis task management for the local Web API."""
from __future__ import annotations

import queue
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pa_agent.api.analysis_stream import StructuredContentBuffer
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
    """Run the production two-stage orchestrator without GUI dependencies."""
    from pa_agent.ai.client_factory import create_ai_client
    from pa_agent.ai.json_validator import JsonValidator
    from pa_agent.ai.prompt_assembler import PromptAssembler
    from pa_agent.ai.router import route_strategy_files
    from pa_agent.config.paths import (
        EXPERIENCE_DIR,
        PROMPT_DIR,
        RECORDS_PENDING_DIR,
        SETTINGS_JSON_PATH,
    )
    from pa_agent.config.settings import load_settings
    from pa_agent.orchestrator.two_stage import TwoStageOrchestrator
    from pa_agent.records.experience_reader import ExperienceReader
    from pa_agent.records.pending_writer import PendingWriter

    settings = load_settings(SETTINGS_JSON_PATH)
    experience_reader = ExperienceReader(experience_dir=EXPERIENCE_DIR)
    orchestrator = TwoStageOrchestrator(
        client=create_ai_client(settings.provider),
        assembler=PromptAssembler(
            prompt_dir=PROMPT_DIR,
            experience_reader=experience_reader,
            prompt_settings=settings.prompt,
        ),
        router=route_strategy_files,
        validator=JsonValidator(settings),
        pending_writer=PendingWriter(
            pending_dir=RECORDS_PENDING_DIR,
            api_key=settings.provider.api_key,
        ),
        exp_reader=experience_reader,
        settings=settings,
    )
    content_buffer = StructuredContentBuffer()
    record = orchestrator.submit(
        frame,
        cancel_token,
        emit,
        on_stage1_reasoning=lambda text: emit(
            {"type": "reasoning_delta", "stage": "stage1", "text": text}
        ),
        on_stage1_content=lambda text: content_buffer.add("stage1", text, emit),
        on_stage2_reasoning=lambda text: emit(
            {"type": "reasoning_delta", "stage": "stage2", "text": text}
        ),
        on_stage2_content=lambda text: content_buffer.add("stage2", text, emit),
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
    content_buffer.finish(emit)
    return record
