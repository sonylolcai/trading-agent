"""Settings routes for the local Web API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import settings_to_payload
from pa_agent.api.market_data import MarketDataError, update_market_selection
from pa_agent.ai.decision_stance import apply_risk_profile
from pa_agent.config.settings import DecisionStance, save_settings

router = APIRouter(prefix="/api", tags=["settings"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


class MarketSelectionUpdate(BaseModel):
    source: str | None = None
    symbol: str | None = None
    timeframe: str | None = None


class RiskProfileUpdate(BaseModel):
    risk_profile: DecisionStance


@router.get("/settings")
def read_settings(request: Request) -> dict:
    return settings_to_payload(_ctx(request).settings)


@router.patch("/settings/market")
def update_market_settings(payload: MarketSelectionUpdate, request: Request) -> dict:
    ctx = _ctx(request)
    try:
        update_market_selection(
            ctx,
            source=payload.source,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return settings_to_payload(ctx.settings)


@router.patch("/settings/risk-profile")
def update_risk_profile(payload: RiskProfileUpdate, request: Request) -> dict:
    ctx = _ctx(request)
    apply_risk_profile(ctx.settings.general, payload.risk_profile)
    if ctx.settings_path is not None:
        save_settings(ctx.settings, ctx.settings_path)
    return settings_to_payload(ctx.settings)
