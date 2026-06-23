from __future__ import annotations

import json
from pathlib import Path

from pa_agent.backtest.record_replay import (
    RecordReplaySummary,
    format_record_replay_summary,
    rebuild_setup_stats_from_records,
)
from pa_agent.backtest.stats_store import SetupStatsLedger
from pa_agent.records.schema import AnalysisRecord, RecordMeta


def _record(
    *,
    ts_ms: int,
    symbol: str,
    bars: list[dict],
    stage2_decision: dict | None,
) -> AnalysisRecord:
    return AnalysisRecord(
        meta=RecordMeta(
            timestamp_local_iso="2026-01-01T00:00:00.000",
            timestamp_local_ms=ts_ms,
            symbol=symbol,
            timeframe="1h",
            bar_count=len(bars),
            ai_provider={},
            decision_stance="balanced",
        ),
        kline_data=bars,
        htf_text="",
        stage1_messages=[],
        stage1_response=None,
        stage1_diagnosis={
            "cycle_position": "broad_channel",
            "direction": "bullish",
            "detected_patterns": ["wide_channel"],
        },
        stage2_messages=[],
        stage2_response=None,
        stage2_decision=stage2_decision,
        strategy_files_used=[],
        experience_loaded=[],
        exception=None,
        usage_total={},
    )


def _bar(ts: float, *, high: float, low: float, close: float) -> dict:
    return {
        "seq": 1,
        "ts_open": ts,
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": 100,
        "closed": True,
    }


def test_rebuild_setup_stats_from_records_simulates_future_bars(tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    records_dir.mkdir()
    output_path = tmp_path / "setup_stats.json"

    trade_record = _record(
        ts_ms=1,
        symbol="BTCUSDT",
        bars=[
            _bar(1_000, high=101, low=99, close=100),
            _bar(0, high=100, low=98, close=99),
        ],
        stage2_decision={
            "decision": {
                "order_direction": "做多",
                "order_type": "市价单",
                "entry_price": 100,
                "take_profit_price": 105,
                "stop_loss_price": 95,
            }
        },
    )
    future_record = _record(
        ts_ms=2,
        symbol="BTCUSDT",
        bars=[
            _bar(2_000, high=106, low=100, close=105),
            _bar(1_000, high=101, low=99, close=100),
        ],
        stage2_decision=None,
    )
    (records_dir / "2026-01-01_00-00-01_BTCUSDT_1h.json").write_text(
        json.dumps(trade_record.model_dump(), ensure_ascii=False),
        encoding="utf-8",
    )
    (records_dir / "2026-01-01_01-00-01_BTCUSDT_1h.json").write_text(
        json.dumps(future_record.model_dump(), ensure_ascii=False),
        encoding="utf-8",
    )

    summary = rebuild_setup_stats_from_records(
        records_dir=records_dir,
        output_path=output_path,
        min_sample_count=1,
    )

    assert summary.records_scanned == 2
    assert summary.trade_signals == 1
    assert summary.completed_trades == 1
    assert summary.setup_buckets == 1
    assert output_path.exists()

    ledger = SetupStatsLedger.load_json(output_path)
    fields = ledger.historical_fields_for_stage1(
        symbol="BTCUSDT",
        timeframe="1h",
        stage1_diagnosis={
            "cycle_position": "broad_channel",
            "direction": "bullish",
            "detected_patterns": ["wide_channel"],
        },
        decision_stance="balanced",
        min_sample_count=1,
    )
    assert fields["estimated_win_rate_basis"] == "historical"
    assert fields["historical_sample_count"] == 1
    assert fields["historical_win_rate_for_this_setup"] == 100.0


def test_rebuild_setup_stats_ignores_open_trades_without_exit(tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    records_dir.mkdir()
    output_path = tmp_path / "setup_stats.json"
    trade_record = _record(
        ts_ms=1,
        symbol="BTCUSDT",
        bars=[_bar(1_000, high=101, low=99, close=100)],
        stage2_decision={
            "decision": {
                "order_direction": "做多",
                "order_type": "市价单",
                "entry_price": 100,
                "take_profit_price": 105,
                "stop_loss_price": 95,
            }
        },
    )
    (records_dir / "2026-01-01_00-00-01_BTCUSDT_1h.json").write_text(
        json.dumps(trade_record.model_dump(), ensure_ascii=False),
        encoding="utf-8",
    )

    summary = rebuild_setup_stats_from_records(records_dir=records_dir, output_path=output_path)

    assert summary.trade_signals == 1
    assert summary.completed_trades == 0
    assert summary.setup_buckets == 0


def test_format_record_replay_summary_mentions_output_path(tmp_path: Path) -> None:
    summary = RecordReplaySummary(
        records_scanned=12,
        trade_signals=5,
        completed_trades=3,
        setup_buckets=2,
        output_path=tmp_path / "setup_stats.json",
    )

    text = format_record_replay_summary(summary)

    assert "扫描记录: 12" in text
    assert "完成交易: 3" in text
    assert "setup_stats.json" in text
