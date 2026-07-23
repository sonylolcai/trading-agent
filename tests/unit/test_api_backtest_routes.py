from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pa_agent.api.app import create_app
from pa_agent.api.context import ApiContext
from pa_agent.backtest.record_replay import RecordReplaySummary
from pa_agent.config.settings import Settings
from pa_agent.data.base import KlineBar
from pa_agent.data.kline_cache import KlineCacheStore


def _context(tmp_path: Path, rebuild: object | None = None) -> ApiContext:
    return ApiContext(
        settings=Settings(),
        kline_cache=KlineCacheStore(tmp_path / "cache"),
        records_dir=tmp_path / "records",
        setup_stats_path=tmp_path / "setup_stats.json",
        rebuild_setup_stats=rebuild or (lambda **_: None),
    )


def _bar(index: int, close: float, *, seq: int = 1) -> KlineBar:
    return KlineBar(
        seq=seq,
        ts_open=float(index * 60_000),
        open=close - 0.4,
        high=close + 0.2,
        low=close - 0.9,
        close=close,
        volume=100.0,
        amount=1000.0,
        closed=True,
    )


def _rising_bars(count: int) -> list[KlineBar]:
    oldest_first = [_bar(i, 100.0 + i, seq=count - i) for i in range(count)]
    return list(reversed(oldest_first))


def test_rebuild_setup_stats_route_uses_injected_paths_and_function(tmp_path: Path) -> None:
    calls: list[dict[str, Path]] = []

    def fake_rebuild(*, records_dir: Path, output_path: Path) -> RecordReplaySummary:
        calls.append({"records_dir": records_dir, "output_path": output_path})
        return RecordReplaySummary(
            records_scanned=5,
            trade_signals=4,
            completed_trades=3,
            setup_buckets=2,
            output_path=output_path,
        )

    context = _context(tmp_path, fake_rebuild)
    client = TestClient(create_app(context))

    response = client.post("/api/backtest/rebuild-setup-stats")

    assert response.status_code == 200
    assert calls == [
        {
            "records_dir": tmp_path / "records",
            "output_path": tmp_path / "setup_stats.json",
        }
    ]
    assert response.json() == {
        "records_scanned": 5,
        "trade_signals": 4,
        "completed_trades": 3,
        "setup_buckets": 2,
        "output_path": "setup_stats.json",
    }


def test_setup_stats_route_returns_compact_rows(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.setup_stats_path.write_text(
        json.dumps(
            {
                "stock|1h|normal_channel|bullish|breakout|l1|balanced": [
                    1.2,
                    -1.0,
                    0.8,
                ],
                "stock|1h|trading_range|neutral|wait|none|balanced": [
                    -1.0,
                    0.2,
                ],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(context))

    response = client.get("/api/backtest/setup-stats")

    assert response.status_code == 200
    payload = response.json()
    rows = payload["rows"]
    assert [row["setup_key"] for row in rows] == [
        "stock|1h|normal_channel|bullish|breakout|l1|balanced",
        "stock|1h|trading_range|neutral|wait|none|balanced",
    ]
    assert rows[0] == {
        "setup_key": "stock|1h|normal_channel|bullish|breakout|l1|balanced",
        "key": "stock|1h|normal_channel|bullish|breakout|l1|balanced",
        "symbol_class": "stock",
        "timeframe_bucket": "1h",
        "cycle_position": "normal_channel",
        "direction": "bullish",
        "order_type": "breakout",
        "patterns": "l1",
        "decision_stance": "balanced",
        "sample_count": 3,
        "wins": 2,
        "losses": 1,
        "total_r": 1.0,
        "win_rate_pct": 66.66666666666666,
        "expectancy_r": 0.3333333333333333,
    }
    assert rows[1]["sample_count"] == 2


def test_rolling_summary_route_returns_empty_summary_without_cache(tmp_path: Path) -> None:
    context = _context(tmp_path)
    client = TestClient(create_app(context))

    response = client.get("/api/backtest/rolling-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "eastmoney"
    assert payload["symbol"] == "000001"
    assert payload["timeframe"] == "1h"
    assert payload["window"] == 100
    assert payload["bar_count"] == 0
    assert payload["trade_signals"] == 0
    assert payload["completed_trades"] == 0
    assert payload["trades"] == []


def test_rolling_summary_route_uses_cached_bars_and_query_window(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        _rising_bars(36),
        max_bars=2000,
    )
    client = TestClient(create_app(context))

    response = client.get("/api/backtest/rolling-summary?window=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "eastmoney"
    assert payload["symbol"] == "000001"
    assert payload["timeframe"] == "1h"
    assert payload["window"] == 30
    assert payload["bar_count"] == 30
    assert payload["evaluated_windows"] > 0
    assert payload["trade_signals"] >= 1
    assert payload["completed_trades"] >= 1
    assert payload["wins"] >= 1
    assert payload["expectancy_r"] == pytest.approx(payload["average_r"])


def test_rolling_summary_route_uses_current_risk_profile(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.settings.general.decision_stance = "aggressive"
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        _rising_bars(36),
        max_bars=2000,
    )
    client = TestClient(create_app(context))

    response = client.get("/api/backtest/rolling-summary?window=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_profile"] == "aggressive"


def test_rolling_comparison_route_returns_both_policies_from_cached_bars(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        _rising_bars(36),
        max_bars=2000,
    )
    client = TestClient(create_app(context))

    response = client.get("/api/backtest/rolling-comparison?window=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "eastmoney"
    assert payload["window"] == 30
    assert payload["price_only"]["bar_count"] == 30
    assert payload["volume_assisted"]["bar_count"] == 30
    assert payload["volume_confirmed"]["bar_count"] == 30
    assert payload["volume_confirmed_time_exit"]["bar_count"] == 30
    assert payload["volume_confirmed_time_exit"]["max_holding_bars"] == 10
    assert "trade_signals" in payload["delta"]
    assert set(payload["volume_contexts"]) == {
        "confirmed",
        "caution",
        "neutral",
        "unavailable",
    }
    assert sum(context["trade_signals"] for context in payload["volume_contexts"].values()) == payload["price_only"]["trade_signals"]
    assert payload["volume_confirmed"]["trade_signals"] == payload["volume_contexts"]["confirmed"]["trade_signals"]
    assert payload["volume_confirmed_time_exit"]["trade_signals"] == payload["volume_confirmed"]["trade_signals"]
