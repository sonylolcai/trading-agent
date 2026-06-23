"""Settings routes for the local Web API."""
from __future__ import annotations

from fastapi import APIRouter, Request

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import settings_to_payload

router = APIRouter(prefix="/api", tags=["settings"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


@router.get("/settings")
def read_settings(request: Request) -> dict:
    return settings_to_payload(_ctx(request).settings)
