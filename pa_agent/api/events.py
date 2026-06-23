"""Event normalization and SSE formatting for API streams."""
from __future__ import annotations

import json
from typing import Any

from pa_agent.util.threading import OrchestratorEvent


_ORCHESTRATOR_EVENT_MAP: dict[OrchestratorEvent, dict[str, Any]] = {
    OrchestratorEvent.Stage1Started: {"type": "stage_started", "stage": "stage1"},
    OrchestratorEvent.Stage1Retry: {"type": "stage_retry", "stage": "stage1"},
    OrchestratorEvent.Stage1Done: {"type": "stage_finished", "stage": "stage1"},
    OrchestratorEvent.Stage1Failed: {"type": "error", "stage": "stage1"},
    OrchestratorEvent.Stage2Started: {"type": "stage_started", "stage": "stage2"},
    OrchestratorEvent.Stage2Retry: {"type": "stage_retry", "stage": "stage2"},
    OrchestratorEvent.Stage2Done: {"type": "stage_finished", "stage": "stage2"},
    OrchestratorEvent.Stage2Failed: {"type": "error", "stage": "stage2"},
    OrchestratorEvent.RecordSaved: {"type": "record_saved"},
    OrchestratorEvent.Cancelled: {"type": "cancelled"},
    OrchestratorEvent.InsufficientData: {
        "type": "error",
        "stage": "preflight",
        "message": "insufficient_data",
    },
}


def normalize_event(event: dict[str, Any] | OrchestratorEvent) -> dict[str, Any]:
    """Convert internal events into the JSON shape consumed by the Web UI."""
    if isinstance(event, OrchestratorEvent):
        return dict(_ORCHESTRATOR_EVENT_MAP[event])
    return dict(event)


def sse_message(event: dict[str, Any]) -> str:
    """Return one normalized Server-Sent Event message frame."""
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"event: message\ndata: {data}\n\n"
