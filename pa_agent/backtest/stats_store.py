"""In-memory setup statistics and historical win-rate fields."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from pa_agent.backtest.setup_key import (
    SetupKey,
    bucket_timeframe,
    classify_symbol,
    normalize_patterns,
)
from pa_agent.backtest.simulator import TradeSimulation


@dataclass(frozen=True)
class SetupStats:
    sample_count: int
    wins: int
    losses: int
    total_r: float

    @property
    def win_rate_pct(self) -> float:
        return self.wins / self.sample_count * 100.0 if self.sample_count else 0.0

    @property
    def expectancy_r(self) -> float:
        return self.total_r / self.sample_count if self.sample_count else 0.0


@dataclass
class SetupStatsLedger:
    """Aggregate completed trade outcomes by setup key."""

    _results: dict[str, list[float]] = field(default_factory=dict)

    def record_result(self, key: SetupKey, result: TradeSimulation) -> None:
        if result.status not in {"win", "loss"}:
            return
        self._results.setdefault(key.as_string(), []).append(float(result.r_multiple))

    def record_many(
        self,
        pairs: Iterable[tuple[SetupKey, TradeSimulation]],
    ) -> None:
        for key, result in pairs:
            self.record_result(key, result)

    @property
    def bucket_count(self) -> int:
        return len(self._results)

    def stats_for(self, key: SetupKey) -> SetupStats:
        values = self._results.get(key.as_string(), [])
        return self._stats_from_values(values)

    @staticmethod
    def _stats_from_values(values: Iterable[float]) -> SetupStats:
        values = list(values)
        wins = sum(1 for value in values if value > 0)
        losses = sum(1 for value in values if value < 0)
        return SetupStats(
            sample_count=len(values),
            wins=wins,
            losses=losses,
            total_r=sum(values),
        )

    @staticmethod
    def _direction_aliases(direction: object) -> set[str]:
        text = str(direction or "").strip().lower()
        if text in {"bullish", "long", "buy", "做多", "多"}:
            return {"bullish", "long", "buy", "做多", "多"}
        if text in {"bearish", "short", "sell", "做空", "空"}:
            return {"bearish", "short", "sell", "做空", "空"}
        return {text} if text else set()

    def stats_for_stage1(
        self,
        *,
        symbol: object,
        timeframe: object,
        stage1_diagnosis: dict,
        decision_stance: str = "conservative",
    ) -> SetupStats:
        symbol_class = classify_symbol(symbol)
        timeframe_bucket = bucket_timeframe(timeframe)
        cycle = str(stage1_diagnosis.get("cycle_position") or "unknown")
        direction_aliases = self._direction_aliases(stage1_diagnosis.get("direction"))
        patterns = set(
            normalize_patterns(
                stage1_diagnosis.get("detected_patterns")
                or stage1_diagnosis.get("patterns")
                or []
            )
        )
        stance = str(decision_stance or "conservative")
        values: list[float] = []
        for key_string, r_values in self._results.items():
            parts = key_string.split("|")
            if len(parts) != 7:
                continue
            (
                key_symbol_class,
                key_timeframe_bucket,
                key_cycle,
                key_direction,
                _key_order_type,
                key_patterns,
                key_stance,
            ) = parts
            if key_symbol_class != symbol_class or key_timeframe_bucket != timeframe_bucket:
                continue
            if key_cycle != cycle or key_stance != stance:
                continue
            if direction_aliases and key_direction not in direction_aliases:
                continue
            key_pattern_set = set(key_patterns.split("+")) if key_patterns != "none" else set()
            if patterns and key_pattern_set and patterns.isdisjoint(key_pattern_set):
                continue
            values.extend(r_values)
        return self._stats_from_values(values)

    def historical_fields_for(
        self,
        key: SetupKey,
        *,
        min_sample_count: int = 20,
    ) -> dict[str, float | int | str | None]:
        stats = self.stats_for(key)
        return self._historical_fields_from_stats(stats, min_sample_count=min_sample_count)

    def historical_fields_for_stage1(
        self,
        *,
        symbol: object,
        timeframe: object,
        stage1_diagnosis: dict,
        decision_stance: str = "conservative",
        min_sample_count: int = 20,
    ) -> dict[str, float | int | str | None]:
        stats = self.stats_for_stage1(
            symbol=symbol,
            timeframe=timeframe,
            stage1_diagnosis=stage1_diagnosis,
            decision_stance=decision_stance,
        )
        return self._historical_fields_from_stats(stats, min_sample_count=min_sample_count)

    @staticmethod
    def _historical_fields_from_stats(
        stats: SetupStats,
        *,
        min_sample_count: int,
    ) -> dict[str, float | int | str | None]:
        if stats.sample_count >= min_sample_count:
            basis = "historical"
        elif stats.sample_count > 0:
            basis = "hybrid"
        else:
            basis = "llm_judgment"
        return {
            "estimated_win_rate_basis": basis,
            "historical_win_rate_for_this_setup": stats.win_rate_pct,
            "historical_sample_count": stats.sample_count,
            "historical_expectancy_r": stats.expectancy_r,
        }

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._results, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> "SetupStatsLedger":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        ledger = cls()
        if isinstance(raw, dict):
            for key, values in raw.items():
                if isinstance(values, list):
                    ledger._results[str(key)] = [float(v) for v in values]
        return ledger
