"""OKX connectivity and crypto portfolio backtest routes."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from pa_agent.api.context import ApiContext
from pa_agent.crypto.backtest import CryptoBacktestConfig, run_okx_crypto_backtest
from pa_agent.crypto.kline_service import get_or_fetch_crypto_klines, seed_default_crypto_cache
from pa_agent.crypto.okx import OkxApiError, read_okx_connection_status

router = APIRouter(prefix="/api/crypto", tags=["crypto"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


class CryptoBacktestRequest(BaseModel):
    years: int = Field(default=5, ge=2, le=8)
    target_volatility: float = Field(default=0.15, ge=0.05, le=0.40)
    cost_bps: float = Field(default=10.0, ge=0, le=100)
    rebalance_days: int = Field(default=7, ge=1, le=30)
    strategy_version: Literal["1.0", "2.0"] = "1.0"


@router.get("/okx/status")
def okx_status() -> dict[str, Any]:
    try:
        return read_okx_connection_status()
    except OkxApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/backtest")
def crypto_backtest(payload: CryptoBacktestRequest) -> dict[str, Any]:
    config = CryptoBacktestConfig(
        years=payload.years,
        target_volatility=payload.target_volatility,
        cost_bps=payload.cost_bps,
        rebalance_days=payload.rebalance_days,
        strategy_version=payload.strategy_version,
    )
    try:
        return run_okx_crypto_backtest(config)
    except OkxApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class CryptoSeedRequest(BaseModel):
    count: int = Field(default=1000, ge=100, le=2000)


@router.get("/klines")
def crypto_klines(
    request: Request,
    symbol: str = Query(default="BTCUSDT"),
    timeframe: str = Query(default="1d"),
    limit: int = Query(default=1000, ge=10, le=3000),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    ctx = _ctx(request)
    output = get_or_fetch_crypto_klines(
        kline_cache=ctx.kline_cache,
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
        refresh=refresh,
    )
    return {
        "symbol": output.symbol,
        "timeframe": output.timeframe,
        "count": output.count,
        "source": output.source,
        "saved_at": output.saved_at,
        "bars": output.bars,
    }


@router.post("/seed-cache")
def crypto_seed_cache(
    request: Request,
    payload: CryptoSeedRequest | None = None,
) -> dict[str, Any]:
    ctx = _ctx(request)
    count = payload.count if payload is not None else 1000
    results = seed_default_crypto_cache(ctx.kline_cache, count=count)
    return {
        "status": "ok",
        "count_per_series": count,
        "seeded_series": results,
    }

