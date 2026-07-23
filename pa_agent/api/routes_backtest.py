"""Backtest setup-statistics routes for the local Web API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import setup_stats_row_to_payload
from pa_agent.api.market_data import current_market_selection
from pa_agent.backtest.rolling import build_rolling_comparison, build_rolling_summary
from pa_agent.backtest.stats_store import SetupStatsLedger
from pa_agent.data.factory import default_symbol_for_kind, normalize_data_source_kind

router = APIRouter(prefix="/api", tags=["backtest"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


def _query_selection(
    ctx: ApiContext,
    *,
    source: str | None,
    symbol: str | None,
    timeframe: str | None,
) -> tuple[str, str, str]:
    current = current_market_selection(ctx)
    kind = normalize_data_source_kind(source) if source is not None else current.source
    source_changed = kind != current.source
    next_symbol = (symbol if symbol is not None else current.symbol).strip()
    if not next_symbol or (source_changed and symbol is None):
        next_symbol = default_symbol_for_kind(kind)
    next_timeframe = (timeframe if timeframe is not None else current.timeframe).strip()
    return kind, next_symbol, next_timeframe or current.timeframe or "1h"


@router.post("/backtest/rebuild-setup-stats")
def rebuild_setup_stats(request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    summary = ctx.rebuild_setup_stats(
        records_dir=ctx.records_dir,
        output_path=ctx.setup_stats_path,
    )
    return {
        "records_scanned": summary.records_scanned,
        "trade_signals": summary.trade_signals,
        "completed_trades": summary.completed_trades,
        "setup_buckets": summary.setup_buckets,
        "output_path": summary.output_path.name,
    }


@router.get("/backtest/setup-stats")
def setup_stats(request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    ledger = SetupStatsLedger.load_json(ctx.setup_stats_path)
    rows = [
        setup_stats_row_to_payload(key, values)
        for key, values in ledger._results.items()
    ]
    rows.sort(key=lambda row: (-row["sample_count"], row["setup_key"]))
    return {"rows": rows}


@router.get("/backtest/rolling-summary")
def rolling_summary(
    request: Request,
    source: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    window: int = Query(default=100, ge=1, le=5000),
) -> dict[str, Any]:
    ctx = _ctx(request)
    selected_source, selected_symbol, selected_timeframe = _query_selection(
        ctx,
        source=source,
        symbol=symbol,
        timeframe=timeframe,
    )
    entry = ctx.kline_cache.read(selected_source, selected_symbol, selected_timeframe)
    summary = build_rolling_summary(
        source=selected_source,
        symbol=selected_symbol,
        timeframe=selected_timeframe,
        bars=entry.bars if entry is not None else (),
        window=window,
        risk_profile=getattr(ctx.settings.general, "decision_stance", None),
    )
    return summary.to_payload()


@router.get("/backtest/rolling-comparison")
def rolling_comparison(
    request: Request,
    source: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    window: int = Query(default=100, ge=1, le=5000),
) -> dict[str, Any]:
    """Compare the baseline price-action proxy against its volume-assisted variant."""
    ctx = _ctx(request)
    selected_source, selected_symbol, selected_timeframe = _query_selection(
        ctx,
        source=source,
        symbol=symbol,
        timeframe=timeframe,
    )
    entry = ctx.kline_cache.read(selected_source, selected_symbol, selected_timeframe)
    comparison = build_rolling_comparison(
        source=selected_source,
        symbol=selected_symbol,
        timeframe=selected_timeframe,
        bars=entry.bars if entry is not None else (),
        window=window,
        risk_profile=getattr(ctx.settings.general, "decision_stance", None),
    )
    return comparison.to_payload()
