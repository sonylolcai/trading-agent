"""FastAPI application factory for the local PA Agent Web API."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pa_agent.api.context import ApiContext
from pa_agent.api.routes_analysis import router as analysis_router
from pa_agent.api.routes_backtest import router as backtest_router
from pa_agent.api.routes_market import router as market_router
from pa_agent.api.routes_records import router as records_router
from pa_agent.api.routes_settings import router as settings_router


def create_app(context: ApiContext | None = None) -> FastAPI:
    app = FastAPI(title="IQ Local API")
    app.state.api_context = context or ApiContext.load()
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
    app.include_router(records_router)
    return app
