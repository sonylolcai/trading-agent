"""OKX connectivity and crypto portfolio backtest routes."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pa_agent.crypto.backtest import CryptoBacktestConfig, run_okx_crypto_backtest
from pa_agent.crypto.okx import OkxApiError, read_okx_connection_status

router = APIRouter(prefix="/api/crypto", tags=["crypto"])


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
