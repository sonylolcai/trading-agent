"""Rebuild setup statistics by replaying saved analysis records."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pa_agent.backtest.setup_key import build_setup_key
from pa_agent.backtest.simulator import TRADE_ORDER_TYPES, simulate_decision
from pa_agent.backtest.stats_store import SetupStatsLedger
from pa_agent.data.base import KlineBar
from pa_agent.data.datetime_ts import ts_open_to_ms
from pa_agent.records.schema import AnalysisRecord


@dataclass(frozen=True)
class RecordReplaySummary:
    records_scanned: int
    trade_signals: int
    completed_trades: int
    setup_buckets: int
    output_path: Path


def format_record_replay_summary(summary: RecordReplaySummary) -> str:
    return (
        "回测统计重建完成\n\n"
        f"扫描记录: {summary.records_scanned}\n"
        f"交易信号: {summary.trade_signals}\n"
        f"完成交易: {summary.completed_trades}\n"
        f"Setup 桶数: {summary.setup_buckets}\n"
        f"输出文件: {summary.output_path}"
    )


def _load_record(path: Path) -> AnalysisRecord | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw.pop("_partial_reason", None)
        return AnalysisRecord.model_validate(raw)
    except Exception:
        return None


def _record_paths(records_dir: Path) -> list[Path]:
    if not records_dir.is_dir():
        return []
    paths = [path for path in records_dir.glob("*.json") if path.is_file()]
    paths.sort(key=lambda path: path.stat().st_mtime)
    return paths


def _closed_bar_from_dict(raw: dict) -> KlineBar | None:
    if not bool(raw.get("closed", True)):
        return None
    try:
        ts_ms = ts_open_to_ms(raw["ts_open"])
        return KlineBar(
            seq=int(raw.get("seq", 1) or 1),
            ts_open=float(ts_ms),
            open=float(raw["open"]),
            high=float(raw["high"]),
            low=float(raw["low"]),
            close=float(raw["close"]),
            volume=float(raw.get("volume", 0.0) or 0.0),
            amount=float(raw.get("amount", 0.0) or 0.0),
            pct_chg=raw.get("pct_chg"),
            closed=True,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _closed_bars(record: AnalysisRecord) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for raw in record.kline_data or []:
        if not isinstance(raw, dict):
            continue
        bar = _closed_bar_from_dict(raw)
        if bar is not None:
            bars.append(bar)
    return bars


def _decision_dict(record: AnalysisRecord) -> dict:
    stage2 = record.stage2_decision
    if not isinstance(stage2, dict):
        return {}
    decision = stage2.get("decision")
    return decision if isinstance(decision, dict) else stage2


def _is_trade_record(record: AnalysisRecord) -> bool:
    return str(_decision_dict(record).get("order_type") or "").strip() in TRADE_ORDER_TYPES


def _group_key(record: AnalysisRecord) -> tuple[str, str]:
    return record.meta.symbol, record.meta.timeframe


def _build_bar_universe(records: Iterable[AnalysisRecord]) -> dict[tuple[str, str], list[KlineBar]]:
    grouped: dict[tuple[str, str], dict[float, KlineBar]] = {}
    for record in records:
        bucket = grouped.setdefault(_group_key(record), {})
        for bar in _closed_bars(record):
            bucket[float(bar.ts_open)] = bar
    return {
        key: [bucket[ts] for ts in sorted(bucket)]
        for key, bucket in grouped.items()
    }


def _latest_closed_ts(record: AnalysisRecord) -> float | None:
    bars = _closed_bars(record)
    if not bars:
        return None
    return max(float(bar.ts_open) for bar in bars)


def _future_bars(record: AnalysisRecord, universe: dict[tuple[str, str], list[KlineBar]]) -> list[KlineBar]:
    cutoff = _latest_closed_ts(record)
    if cutoff is None:
        return []
    return [
        bar
        for bar in universe.get(_group_key(record), [])
        if float(bar.ts_open) > cutoff
    ]


def rebuild_setup_stats_from_records(
    *,
    records_dir: Path | None = None,
    output_path: Path | None = None,
    min_sample_count: int = 20,
) -> RecordReplaySummary:
    """Replay saved records and write a setup statistics ledger.

    This is an offline/manual operation. It does not call the LLM; it only
    evaluates Stage 2 trade plans against later K-lines already present in
    saved records for the same symbol and timeframe.
    """
    from pa_agent.config.paths import RECORDS_PENDING_DIR, SETUP_STATS_JSON_PATH

    records_root = records_dir or RECORDS_PENDING_DIR
    target = output_path or SETUP_STATS_JSON_PATH
    records = [
        record
        for record in (_load_record(path) for path in _record_paths(records_root))
        if record is not None and record.exception is None
    ]
    universe = _build_bar_universe(records)
    ledger = SetupStatsLedger()
    trade_signals = 0
    completed_trades = 0

    for record in records:
        if not _is_trade_record(record):
            continue
        trade_signals += 1
        result = simulate_decision(_decision_dict(record), _future_bars(record, universe))
        if result.status not in {"win", "loss"}:
            continue
        key = build_setup_key(
            symbol=record.meta.symbol,
            timeframe=record.meta.timeframe,
            stage1_diagnosis=record.stage1_diagnosis,
            stage2_decision=record.stage2_decision,
            decision_stance=record.meta.decision_stance,
        )
        ledger.record_result(key, result)
        completed_trades += 1

    _ = min_sample_count  # kept for future report thresholds; ledger stores all samples.
    ledger.save_json(target)
    return RecordReplaySummary(
        records_scanned=len(records),
        trade_signals=trade_signals,
        completed_trades=completed_trades,
        setup_buckets=ledger.bucket_count,
        output_path=target,
    )
