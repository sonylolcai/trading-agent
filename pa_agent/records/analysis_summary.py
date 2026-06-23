"""Compact timeline summaries for saved analysis records."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pa_agent.config.paths import RECORDS_PENDING_DIR


@dataclass(frozen=True)
class AnalysisSummary:
    path: Path
    timestamp_local_iso: str
    timestamp_local_ms: int
    source: str
    symbol: str
    timeframe: str
    status: str
    cycle_position: str
    direction: str
    order_type: str
    trade_confidence: int | None
    win_rate_basis: str
    historical_sample_count: int | None
    error_message: str


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _decision(raw: dict[str, Any]) -> dict[str, Any]:
    stage2 = _as_dict(raw.get("stage2_decision"))
    decision = stage2.get("decision")
    return decision if isinstance(decision, dict) else stage2


def _status_and_error(raw: dict[str, Any]) -> tuple[str, str]:
    partial_reason = raw.get("_partial_reason")
    if partial_reason:
        return "partial", str(partial_reason)

    exception = raw.get("exception")
    if isinstance(exception, dict):
        message = exception.get("message") or exception.get("error") or exception.get("type")
        return "failed", str(message or exception)
    if exception:
        return "failed", str(exception)
    return "success", ""


def _summary_from_raw(path: Path, raw: dict[str, Any]) -> AnalysisSummary:
    meta = _as_dict(raw.get("meta"))
    stage1 = _as_dict(raw.get("stage1_diagnosis"))
    decision = _decision(raw)
    status, error_message = _status_and_error(raw)

    return AnalysisSummary(
        path=path,
        timestamp_local_iso=str(meta.get("timestamp_local_iso", "")),
        timestamp_local_ms=int(meta.get("timestamp_local_ms", 0) or 0),
        source=str(meta.get("source") or meta.get("data_source") or ""),
        symbol=str(meta.get("symbol", "")),
        timeframe=str(meta.get("timeframe", "")),
        status=status,
        cycle_position=str(stage1.get("cycle_position") or stage1.get("market_phase") or ""),
        direction=str(decision.get("direction") or decision.get("trade_direction") or ""),
        order_type=str(decision.get("order_type") or decision.get("action") or ""),
        trade_confidence=_as_int_or_none(decision.get("trade_confidence")),
        win_rate_basis=str(decision.get("estimated_win_rate_basis") or ""),
        historical_sample_count=_as_int_or_none(decision.get("historical_sample_count")),
        error_message=error_message,
    )


def read_analysis_summaries(
    directory: Path | None = None,
    *,
    limit: int = 200,
) -> list[AnalysisSummary]:
    root = directory or RECORDS_PENDING_DIR
    if limit <= 0 or not root.is_dir():
        return []

    rows: list[AnalysisSummary] = []
    for path in root.glob("*.json"):
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        try:
            rows.append(_summary_from_raw(path, raw))
        except (TypeError, ValueError):
            continue

    rows.sort(
        key=lambda row: (row.timestamp_local_ms, row.path.stat().st_mtime),
        reverse=True,
    )
    return rows[:limit]
