import json

from pa_agent.records.analysis_summary import read_analysis_summaries


def _record(ts_ms: int, symbol: str = "000001", *, exception: dict | None = None) -> dict:
    return {
        "meta": {
            "timestamp_local_iso": "2026-06-23T10:00:00+08:00",
            "timestamp_local_ms": ts_ms,
            "symbol": symbol,
            "timeframe": "1h",
            "bar_count": 100,
            "ai_provider": {"model": "test"},
            "decision_stance": "balanced",
        },
        "kline_data": [],
        "htf_text": "",
        "stage1_messages": [],
        "stage1_response": {},
        "stage1_diagnosis": {
            "cycle_position": "trading_range",
            "current_bias": "neutral",
        },
        "stage2_messages": [],
        "stage2_response": {},
        "stage2_decision": {
            "decision": {
                "direction": "long",
                "order_type": "wait",
                "trade_confidence": 55,
                "estimated_win_rate_basis": "historical",
                "historical_sample_count": 47,
            }
        },
        "strategy_files_used": [],
        "experience_loaded": [],
        "exception": exception,
        "usage_total": {},
    }


def test_read_summaries_newest_first(tmp_path):
    (tmp_path / "old.json").write_text(json.dumps(_record(1000)), encoding="utf-8")
    (tmp_path / "new.json").write_text(
        json.dumps(_record(2000, symbol="000002")), encoding="utf-8"
    )

    rows = read_analysis_summaries(tmp_path, limit=10)

    assert [row.symbol for row in rows] == ["000002", "000001"]
    assert rows[0].order_type == "wait"
    assert rows[0].cycle_position == "trading_range"
    assert rows[0].direction == "long"
    assert rows[0].trade_confidence == 55
    assert rows[0].win_rate_basis == "historical"
    assert rows[0].historical_sample_count == 47
    assert rows[0].status == "success"


def test_read_summaries_marks_partial_record(tmp_path):
    raw = _record(1000, exception={"stage": "stage2", "message": "bad json"})
    raw["_partial_reason"] = "stage2 validation failed"
    (tmp_path / "partial.json").write_text(json.dumps(raw), encoding="utf-8")

    rows = read_analysis_summaries(tmp_path, limit=10)

    assert len(rows) == 1
    assert rows[0].status == "partial"
    assert "stage2 validation failed" in rows[0].error_message


def test_read_summaries_skips_corrupt_json(tmp_path):
    (tmp_path / "broken.json").write_text("{bad-json", encoding="utf-8")
    (tmp_path / "ok.json").write_text(json.dumps(_record(1000)), encoding="utf-8")

    rows = read_analysis_summaries(tmp_path, limit=10)

    assert len(rows) == 1
    assert rows[0].symbol == "000001"


def test_read_summaries_respects_limit(tmp_path):
    for index in range(3):
        (tmp_path / f"{index}.json").write_text(json.dumps(_record(index)), encoding="utf-8")

    rows = read_analysis_summaries(tmp_path, limit=2)

    assert len(rows) == 2
    assert [row.timestamp_local_ms for row in rows] == [2, 1]
