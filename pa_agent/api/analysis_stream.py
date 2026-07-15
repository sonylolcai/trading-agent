"""Helpers for structured analysis stream events."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


EmitEvent = Callable[[dict[str, Any]], None]


@dataclass
class _StageContent:
    chunks: list[str] = field(default_factory=list)
    started: bool = False
    finished: bool = False


class StructuredContentBuffer:
    """Wrap streamed model JSON content with explicit start and finish markers."""

    def __init__(self, *, content_format: str = "json") -> None:
        self._content_format = content_format
        self._stages: dict[str, _StageContent] = {}

    def add(self, stage: str, text: str, emit: EmitEvent) -> None:
        if not text:
            return
        content = self._stages.setdefault(stage, _StageContent())
        if not content.started:
            content.started = True
            emit({"type": "content_started", "stage": stage, "format": self._content_format})
        content.chunks.append(text)
        emit({"type": "content_delta", "stage": stage, "text": text})

    def finish(self, emit: EmitEvent) -> None:
        for stage, content in self._stages.items():
            if not content.started or content.finished:
                continue
            content.finished = True
            emit(
                {
                    "type": "content_finished",
                    "stage": stage,
                    "format": self._content_format,
                    "text": "".join(content.chunks),
                }
            )
