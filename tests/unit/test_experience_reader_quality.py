from __future__ import annotations

import json
from pathlib import Path

from pa_agent.records.experience_reader import ExperienceReader


def _write_case(
    root: Path,
    cycle: str,
    bucket: str,
    filename: str,
    content: dict,
) -> None:
    target = root / cycle / bucket
    target.mkdir(parents=True, exist_ok=True)
    (target / filename).write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")


def test_read_for_stage2_requires_outcome_and_balances_winners_and_losers(tmp_path: Path) -> None:
    setup_key = "crypto|1h|broad_channel|做多|突破单|wide_channel|balanced"
    _write_case(
        tmp_path,
        "broad_channel",
        "success_cases",
        "2026-01-03_10-00-00_BTCUSD_1h.json",
        {
            "setup_key": setup_key,
            "direction": "做多",
            "detected_patterns": ["wide_channel"],
            "outcome": {"label": "win", "r_multiple": 1.2},
        },
    )
    _write_case(
        tmp_path,
        "broad_channel",
        "failure_cases",
        "2026-01-02_10-00-00_BTCUSD_1h.json",
        {
            "setup_key": setup_key,
            "direction": "做多",
            "detected_patterns": ["wide_channel"],
            "outcome": {"label": "loss", "r_multiple": -1.0, "exit_reason": "stop_loss"},
        },
    )
    _write_case(
        tmp_path,
        "broad_channel",
        "success_cases",
        "2026-01-04_10-00-00_BTCUSD_1h.json",
        {
            "setup_key": setup_key,
            "direction": "做多",
            "detected_patterns": ["wide_channel"],
            "terminal": {"outcome": "wait"},
        },
    )

    entries = ExperienceReader(tmp_path).read_for_stage2(
        "broad_channel",
        direction="做多",
        patterns=["wide_channel"],
        setup_key=setup_key,
        max_entries=4,
        require_outcome=True,
        include_winners=True,
        include_losers=True,
    )

    assert [entry.case_type for entry in entries] == ["success", "failure"]
    assert all("outcome" in entry.content for entry in entries)


def test_read_for_stage2_can_select_only_losers(tmp_path: Path) -> None:
    setup_key = "forex|15m|trading_range|做空|限价单|double_top|conservative"
    _write_case(
        tmp_path,
        "trading_range",
        "success_cases",
        "2026-01-03_10-00-00_XAUUSD_15m.json",
        {"setup_key": setup_key, "direction": "做空", "outcome": {"r_multiple": 0.8}},
    )
    _write_case(
        tmp_path,
        "trading_range",
        "failure_cases",
        "2026-01-04_10-00-00_XAUUSD_15m.json",
        {"setup_key": setup_key, "direction": "做空", "outcome": {"r_multiple": -1.0}},
    )

    entries = ExperienceReader(tmp_path).read_for_stage2(
        "trading_range",
        direction="做空",
        setup_key=setup_key,
        max_entries=3,
        include_winners=False,
        include_losers=True,
    )

    assert len(entries) == 1
    assert entries[0].case_type == "failure"
