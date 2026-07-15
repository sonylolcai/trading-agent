from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from pa_agent.api import app as api_app_module
from pa_agent.api.app import create_app
from pa_agent.api.context import ApiContext
from pa_agent.config.settings import Settings
from pa_agent.data.base import KlineBar
from pa_agent.data.kline_cache import KlineCacheStore
from pa_agent.util.mask_secret import mask_secret


def _context(tmp_path: Path) -> ApiContext:
    settings = Settings()
    settings.provider.api_key = "sk-test-secret"
    settings.general.last_data_source = "eastmoney"
    settings.general.last_symbol = "000001"
    settings.general.last_timeframe = "1h"
    settings.general.analysis_bar_count = 2
    return ApiContext(
        settings=settings,
        kline_cache=KlineCacheStore(tmp_path / "cache"),
        records_dir=tmp_path / "records",
    )


def _bar(seq: int, ts: float, close: float, *, closed: bool = True) -> KlineBar:
    return KlineBar(seq, ts, close - 1, close + 1, close - 2, close, 100, closed=closed)


def _recent_hourly_bars() -> list[KlineBar]:
    now_ms = int(time.time() * 1000)
    hour_ms = 60 * 60 * 1000
    return [
        _bar(0, now_ms, 14, closed=False),
        _bar(1, now_ms - hour_ms, 13),
        _bar(2, now_ms - 2 * hour_ms, 12),
    ]


def test_settings_route_masks_api_key(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["provider"]["api_key"] == mask_secret("sk-test-secret")


def test_app_module_does_not_construct_production_app_on_import() -> None:
    assert not hasattr(api_app_module, "app")


def test_data_sources_route_lists_default_sources(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/data-sources")

    assert response.status_code == 200
    kinds = [item["kind"] for item in response.json()["items"]]
    assert kinds[:3] == ["eastmoney", "akshare", "tushare"]
    assert "mt5" in kinds


def test_timeframes_route_uses_source_supported_values(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/timeframes?source=eastmoney")

    assert response.status_code == 200
    assert "1w" in response.json()["items"]
    assert "1M" in response.json()["items"]


def test_market_selection_route_updates_current_source_symbol_and_timeframe(tmp_path: Path) -> None:
    context = _context(tmp_path)
    client = TestClient(create_app(context))

    response = client.patch(
        "/api/settings/market",
        json={
            "source": "tradingview",
            "symbol": "XAUUSD",
            "timeframe": "15m",
        },
    )

    assert response.status_code == 200
    assert response.json()["general"]["last_data_source"] == "tradingview"
    assert response.json()["general"]["last_symbol"] == "XAUUSD"
    assert response.json()["general"]["last_timeframe"] == "15m"
    assert context.settings.general.last_data_source == "tradingview"
    assert context.settings.general.last_symbol == "XAUUSD"
    assert context.settings.general.last_timeframe == "15m"


def test_market_snapshot_reads_cache_and_keeps_newest_first(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        _recent_hourly_bars(),
        max_bars=20,
    )
    client = TestClient(create_app(context))

    response = client.get("/api/market/snapshot?bars=2&include_forming=false")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "cache"
    assert payload["frame"]["order"] == "newest_first"
    assert [bar["seq"] for bar in payload["frame"]["bars"]] == [1, 2]
    assert [bar["close"] for bar in payload["frame"]["bars"]] == [13, 12]


def test_market_snapshot_clamps_requested_bars_to_cached_closed_bars(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        _recent_hourly_bars(),
        max_bars=20,
    )
    client = TestClient(create_app(context))

    response = client.get("/api/market/snapshot?bars=100&include_forming=false")

    assert response.status_code == 200
    assert [bar["seq"] for bar in response.json()["frame"]["bars"]] == [1, 2]


def test_market_snapshot_can_include_forming_bar_for_display(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        _recent_hourly_bars(),
        max_bars=20,
    )
    client = TestClient(create_app(context))

    response = client.get("/api/market/snapshot?bars=2&include_forming=true")

    assert response.status_code == 200
    payload = response.json()
    assert [bar["seq"] for bar in payload["frame"]["bars"]] == [0, 1, 2]


def test_records_route_returns_empty_list_when_no_records(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/records")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_records_route_rejects_negative_limit(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/records?limit=-1")

    assert response.status_code == 422
