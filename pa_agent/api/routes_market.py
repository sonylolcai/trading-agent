"""Market metadata and snapshot routes for the local Web API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import frame_to_payload
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
    normalize_data_source_kind(source)
    return {"items": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]}


@router.get("/kline-cache")
def read_kline_cache(request: Request) -> dict:
    ctx = _ctx(request)
    general = ctx.settings.general
    kind = normalize_data_source_kind(general.last_data_source)
    entry = ctx.kline_cache.read(kind, general.last_symbol, general.last_timeframe)
    if entry is None:
        return {
            "available": False,
            "source": kind,
            "symbol": general.last_symbol,
            "timeframe": general.last_timeframe,
        }
    return {
        "available": True,
        "source": entry.source,
        "symbol": entry.symbol,
        "timeframe": entry.timeframe,
        "saved_at": entry.saved_at,
        "bar_count": len(entry.bars),
    }


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
