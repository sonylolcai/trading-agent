"""FastAPI application factory for the local PA Agent Web API."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pa_agent.api.context import ApiContext
from pa_agent.api.routes_analysis import router as analysis_router
from pa_agent.api.routes_backtest import router as backtest_router
from pa_agent.api.routes_crypto import router as crypto_router
from pa_agent.api.routes_market import router as market_router
from pa_agent.api.routes_records import router as records_router
from pa_agent.api.routes_settings import router as settings_router


def create_app(context: ApiContext | None = None) -> FastAPI:
    ctx = context or ApiContext.load()

    # Ensure crypto K-line cache is pre-seeded on startup if empty (zero deployment maintenance)
    try:
        from pa_agent.crypto.kline_service import seed_default_crypto_cache

        crypto_dir = ctx.kline_cache.root / "crypto"
        if not crypto_dir.exists() or not any(crypto_dir.glob("*.json")):
            seed_default_crypto_cache(ctx.kline_cache, count=1000)
    except Exception:
        pass

    app = FastAPI(title="IQ Local API")
    app.state.api_context = ctx
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            "https://for-one-dream.cloud",
            "https://www.for-one-dream.cloud",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(settings_router)
    app.include_router(market_router)
    app.include_router(analysis_router)
    app.include_router(backtest_router)
    app.include_router(crypto_router)
    app.include_router(records_router)
    return app
