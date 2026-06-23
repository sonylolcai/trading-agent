"""Small backtest engine that simulates prepared Stage 2 cases."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pa_agent.backtest.metrics import BacktestMetrics, calculate_metrics
from pa_agent.backtest.setup_key import SetupKey
from pa_agent.backtest.simulator import TradeSimulation, simulate_decision
from pa_agent.backtest.stats_store import SetupStatsLedger
from pa_agent.data.base import KlineBar


@dataclass(frozen=True)
class BacktestCase:
    decision: dict[str, Any]
    future_bars: tuple[KlineBar, ...]
    setup_key: SetupKey | None = None
    label: str = ""


@dataclass(frozen=True)
class BacktestRun:
    results: tuple[TradeSimulation, ...]
    metrics: BacktestMetrics
    setup_stats: SetupStatsLedger


class BacktestEngine:
    """Run conservative simulations over prepared cases."""

    def run(self, cases: Iterable[BacktestCase]) -> BacktestRun:
        results: list[TradeSimulation] = []
        ledger = SetupStatsLedger()
        for case in cases:
            result = simulate_decision(case.decision, case.future_bars)
            results.append(result)
            if case.setup_key is not None:
                ledger.record_result(case.setup_key, result)
        return BacktestRun(
            results=tuple(results),
            metrics=calculate_metrics(results),
            setup_stats=ledger,
        )
