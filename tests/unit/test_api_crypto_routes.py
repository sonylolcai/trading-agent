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


def test_crypto_klines_route_returns_bars_and_persists(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/crypto/klines?symbol=BTCUSDT&timeframe=1d&limit=100")
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "BTCUSDT"
    assert payload["timeframe"] == "1d"
    assert payload["count"] == 100
    assert len(payload["bars"]) == 100
    assert "time" in payload["bars"][0]
    assert "open" in payload["bars"][0]
    assert "close" in payload["bars"][0]

    # Subsequent call reads from backend_cache
    response2 = client.get("/api/crypto/klines?symbol=BTCUSDT&timeframe=1d&limit=50")
    assert response2.status_code == 200
    assert response2.json()["source"] == "backend_cache"
    assert response2.json()["count"] == 50


def test_crypto_seed_cache_route(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.post("/api/crypto/seed-cache", json={"count": 100})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["count_per_series"] == 100
    assert "BTCUSDT_1d" in payload["seeded_series"]


def test_create_app_cold_start_auto_seeds_crypto_cache(tmp_path: Path) -> None:
    """Verifies that a server deployed from scratch with zero cache files auto-seeds default crypto data on app startup."""
    cache_root = tmp_path / "fresh_cache"
    assert not cache_root.exists()

    ctx = ApiContext(
        settings=Settings(),
        kline_cache=KlineCacheStore(cache_root),
        records_dir=tmp_path / "records",
    )
    # create_app triggers the startup auto-seed
    client = TestClient(create_app(ctx))

    # Assert cache files were automatically created
    crypto_dir = cache_root / "crypto"
    assert crypto_dir.exists()
    assert (crypto_dir / "BTCUSDT_1d.json").exists()
    assert (crypto_dir / "ETHUSDT_1h.json").exists()

    # Querying the endpoint immediately serves from backend_cache
    res = client.get("/api/crypto/klines?symbol=BTCUSDT&timeframe=1d&limit=500")
    assert res.status_code == 200
    assert res.json()["source"] == "backend_cache"
    assert res.json()["count"] == 500


