"""Analysis record routes for the local Web API."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import record_summary_to_payload
from pa_agent.records.analysis_history import list_record_paths, load_record

router = APIRouter(prefix="/api", tags=["records"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


@router.get("/records")
def list_records(
    request: Request,
    limit: int = Query(default=200, ge=0, le=1000),
) -> dict[str, list[dict]]:
    ctx = _ctx(request)
    items: list[dict] = []
    for path in list_record_paths(ctx.records_dir)[:limit]:
        record = load_record(path)
        if record is None:
            continue
        items.append(record_summary_to_payload(path, record))
    return {"items": items}
