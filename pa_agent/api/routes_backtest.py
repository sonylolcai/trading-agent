"""Backtest setup-statistics routes for the local Web API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import setup_stats_row_to_payload
from pa_agent.backtest.stats_store import SetupStatsLedger

router = APIRouter(prefix="/api", tags=["backtest"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


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
