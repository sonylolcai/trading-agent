"""PA Agent utility package."""

from pa_agent.util.threading import CancelToken, OrchestratorEvent
from pa_agent.util.logging import configure_logging, update_api_key

# EventBus requires PyQt6 — only import when available (GUI builds)
def _get_event_bus():
    from pa_agent.util.event_bus import EventBus
    return EventBus

__all__ = ["CancelToken", "OrchestratorEvent", "configure_logging", "update_api_key"]
