"""Market metadata and snapshot routes for the local Web API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import frame_to_payload
from pa_agent.api.market_data import (
    MarketDataError,
    fetch_and_cache_kline_data,
    supported_timeframes_for_source,
    update_market_selection,
)
from pa_agent.data.factory import (
    DATA_SOURCE_CHOICES,
    data_source_label,
    default_symbol_for_kind,
    normalize_data_source_kind,
)
from pa_agent.data.bar_close_wait import has_forming_bar_at_head
from pa_agent.data.snapshot import build_analysis_frame, build_live_frame

router = APIRouter(prefix="/api", tags=["market"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


class MarketFetchRequest(BaseModel):
    source: str | None = None
    symbol: str | None = None
    timeframe: str | None = None


def _cache_payload(
    *,
    available: bool,
    source: str,
    symbol: str,
    timeframe: str,
    saved_at: str | None = None,
    bar_count: int | None = None,
) -> dict:
    payload = {
        "available": available,
        "source": source,
        "symbol": symbol,
        "timeframe": timeframe,
    }
    if saved_at is not None:
        payload["saved_at"] = saved_at
    if bar_count is not None:
        payload["bar_count"] = bar_count
    return payload


@router.get("/data-sources")
def list_data_sources() -> dict[str, list[dict[str, str]]]:
    return {
        "items": [
            {
                "kind": kind,
                "label": data_source_label(kind),
                "default_symbol": default_symbol_for_kind(kind),
            }
            for kind, _label in DATA_SOURCE_CHOICES
        ]
    }


@router.get("/timeframes")
def list_timeframes(source: str | None = None) -> dict[str, list[str]]:
    return {"items": supported_timeframes_for_source(source)}


@router.get("/kline-cache")
def read_kline_cache(request: Request) -> dict:
    ctx = _ctx(request)
    general = ctx.settings.general
    kind = normalize_data_source_kind(general.last_data_source)
    entry = ctx.kline_cache.read(kind, general.last_symbol, general.last_timeframe)
    if entry is None:
        return _cache_payload(
            available=False,
            source=kind,
            symbol=general.last_symbol,
            timeframe=general.last_timeframe,
        )
    return _cache_payload(
        available=True,
        source=entry.source,
        symbol=entry.symbol,
        timeframe=entry.timeframe,
        saved_at=entry.saved_at,
        bar_count=len(entry.bars),
    )


@router.post("/market/fetch")
def fetch_market_data(payload: MarketFetchRequest, request: Request) -> dict:
    ctx = _ctx(request)
    try:
        update_market_selection(
            ctx,
            source=payload.source,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
        )
        entry = fetch_and_cache_kline_data(ctx)
    except MarketDataError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _cache_payload(
        available=True,
        source=entry.source,
        symbol=entry.symbol,
        timeframe=entry.timeframe,
        saved_at=entry.saved_at,
        bar_count=len(entry.bars),
    )


@router.get("/market/snapshot")
def read_market_snapshot(
    request: Request,
    bars: int = Query(default=100, ge=1, le=5000),
    include_forming: bool = False,
) -> dict:
    ctx = _ctx(request)
    general = ctx.settings.general
    kind = normalize_data_source_kind(general.last_data_source)
    entry = ctx.kline_cache.read(kind, general.last_symbol, general.last_timeframe)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="No cached K-line data for current source/symbol/timeframe",
        )

    raw_bars = list(entry.bars)
    has_forming = has_forming_bar_at_head(
        raw_bars,
        entry.timeframe,
        symbol=entry.symbol,
    )
    available_closed = len(raw_bars) - (1 if has_forming else 0)
    closed_count = min(bars, available_closed)
    if closed_count < 1:
        raise HTTPException(status_code=422, detail="Not enough bars to build snapshot")

    if include_forming:
        frame = build_live_frame(raw_bars, closed_count, entry.symbol, entry.timeframe)
    else:
        frame = build_analysis_frame(raw_bars, closed_count, entry.symbol, entry.timeframe)
    if frame is None:
        raise HTTPException(status_code=422, detail="Not enough bars to build snapshot")
    return {
        "source": "cache",
        "cache_saved_at": entry.saved_at,
        "frame": frame_to_payload(frame),
    }
