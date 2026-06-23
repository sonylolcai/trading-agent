from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from pa_agent.api.app import create_app
from pa_agent.api.context import ApiContext
from pa_agent.backtest.record_replay import RecordReplaySummary
from pa_agent.config.settings import Settings
from pa_agent.data.kline_cache import KlineCacheStore


def _context(tmp_path: Path, rebuild: object | None = None) -> ApiContext:
    return ApiContext(
        settings=Settings(),
        kline_cache=KlineCacheStore(tmp_path / "cache"),
        records_dir=tmp_path / "records",
        setup_stats_path=tmp_path / "setup_stats.json",
        rebuild_setup_stats=rebuild or (lambda **_: None),
    )


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
