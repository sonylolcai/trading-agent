from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from pa_agent.api import routes_crypto
from pa_agent.api.app import create_app
from pa_agent.api.context import ApiContext
from pa_agent.config.settings import Settings
from pa_agent.data.kline_cache import KlineCacheStore


def _context(tmp_path: Path) -> ApiContext:
    return ApiContext(
        settings=Settings(),
        kline_cache=KlineCacheStore(tmp_path / "cache"),
        records_dir=tmp_path / "records",
    )


def test_crypto_backtest_route_validates_and_passes_config(tmp_path: Path, monkeypatch) -> None:
    captured = []

    def fake_runner(config):
        captured.append(config)
        return {"metrics": {"total_return": 0.25}}

    monkeypatch.setattr(routes_crypto, "run_okx_crypto_backtest", fake_runner)
    client = TestClient(create_app(_context(tmp_path)))

    response = client.post(
        "/api/crypto/backtest",
        json={
            "years": 4,
            "target_volatility": 0.12,
            "cost_bps": 14,
            "rebalance_days": 5,
            "strategy_version": "2.0",
        },
    )

    assert response.status_code == 200
    assert response.json()["metrics"]["total_return"] == 0.25
    assert captured[0].years == 4
    assert captured[0].target_volatility == 0.12
    assert captured[0].cost_bps == 14
    assert captured[0].rebalance_days == 5
    assert captured[0].strategy_version == "2.0"


def test_crypto_backtest_route_rejects_unsafe_parameters(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.post("/api/crypto/backtest", json={"cost_bps": -1})

    assert response.status_code == 422


def test_okx_status_route_returns_safe_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        routes_crypto,
        "read_okx_connection_status",
        lambda: {
            "provider": "OKX",
            "mode": "demo",
            "credentials_configured": False,
            "public_api_reachable": True,
            "authenticated": False,
        },
    )
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/crypto/okx/status")

    assert response.status_code == 200
    assert response.json()["credentials_configured"] is False
    assert "api_key" not in response.json()
