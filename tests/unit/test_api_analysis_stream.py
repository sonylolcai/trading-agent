from __future__ import annotations

from typing import Any

from pa_agent.api.analysis_stream import StructuredContentBuffer


def test_structured_content_buffer_wraps_json_stage_chunks() -> None:
    events: list[dict[str, Any]] = []
    buffer = StructuredContentBuffer()

    buffer.add("stage1", '{"cycle":', events.append)
    buffer.add("stage1", '"up"}', events.append)
    buffer.finish(events.append)

    assert events == [
        {"type": "content_started", "stage": "stage1", "format": "json"},
        {"type": "content_delta", "stage": "stage1", "text": '{"cycle":'},
        {"type": "content_delta", "stage": "stage1", "text": '"up"}'},
        {
            "type": "content_finished",
            "stage": "stage1",
            "format": "json",
            "text": '{"cycle":"up"}',
        },
    ]


def test_structured_content_buffer_finishes_each_started_stage_once() -> None:
    events: list[dict[str, Any]] = []
    buffer = StructuredContentBuffer()

    buffer.add("stage1", "a", events.append)
    buffer.add("stage2", "b", events.append)
    buffer.finish(events.append)
    buffer.finish(events.append)

    finished = [event for event in events if event["type"] == "content_finished"]
    assert finished == [
        {"type": "content_finished", "stage": "stage1", "format": "json", "text": "a"},
        {"type": "content_finished", "stage": "stage2", "format": "json", "text": "b"},
    ]
