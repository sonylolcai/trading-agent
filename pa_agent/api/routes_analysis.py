"""Analysis task routes for the local Web API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import analysis_record_to_payload, frame_to_payload
from pa_agent.data.snapshot import build_analysis_frame

router = APIRouter(prefix="/api", tags=["analysis"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


def _task_payload(task: Any) -> dict[str, Any]:
    record = None if task.record is None else analysis_record_to_payload(task.record)
    record_summary = None
    stage2_decision = None
    usage_total = None
    if record is not None:
        record_summary = {
            "timestamp_local_iso": record["timestamp_local_iso"],
            "timestamp_local_ms": record["timestamp_local_ms"],
            "symbol": record["symbol"],
            "timeframe": record["timeframe"],
            "bar_count": record["bar_count"],
            "decision_stance": record["decision_stance"],
        }
        stage2_decision = record["stage2_decision"]
        usage_total = record["usage_total"]
    error = task.error
    if error is None and record is not None and isinstance(record.get("exception"), dict):
        exception = record["exception"]
        error = exception.get("message") or exception.get("type")

    return {
        "analysis_id": task.analysis_id,
        "status": task.status,
        "created_at_ms": task.created_at_ms,
        "updated_at_ms": task.updated_at_ms,
        "event_count": len(task.events),
        "event_url": f"/api/analysis/{task.analysis_id}/events",
        "frame": frame_to_payload(task.frame),
        "record": record,
        "record_summary": record_summary,
        "stage2_decision": stage2_decision,
        "usage_total": usage_total,
        "error": error,
    }


@router.post("/analysis", status_code=202)
def start_analysis(request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    settings = ctx.settings
    source = str(settings.general.last_data_source)
    symbol = settings.general.last_symbol
    timeframe = settings.general.last_timeframe
    entry = ctx.kline_cache.read(source, symbol, timeframe)
    if entry is None:
        raise HTTPException(status_code=404, detail="No cached K-line snapshot found")

    bar_count = int(settings.general.analysis_bar_count)
    frame = build_analysis_frame(list(entry.bars), bar_count, symbol, timeframe)
    if frame is None:
        raise HTTPException(
            status_code=422,
            detail=f"Need at least {bar_count} closed bars in cache",
        )

    task = ctx.analysis_tasks.start(frame, ctx.analysis_runner)
    payload = _task_payload(task)
    payload["status"] = "running"
    return payload


@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str, request: Request) -> dict[str, Any]:
    task = _ctx(request).analysis_tasks.get(analysis_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")
    return _task_payload(task)


@router.delete("/analysis/{analysis_id}")
def cancel_analysis(analysis_id: str, request: Request) -> dict[str, Any]:
    task = _ctx(request).analysis_tasks.cancel(analysis_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")
    return _task_payload(task)


@router.get("/analysis/{analysis_id}/events")
def stream_analysis_events(analysis_id: str, request: Request) -> StreamingResponse:
    store = _ctx(request).analysis_tasks
    if store.get(analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")
    return StreamingResponse(
        store.sse_events(analysis_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
