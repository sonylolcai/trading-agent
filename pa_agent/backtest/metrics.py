"""Backtest aggregate metrics."""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Iterable

from pa_agent.backtest.simulator import TradeSimulation


@dataclass(frozen=True)
class BacktestMetrics:
    total_signals: int
    triggered_trades: int
    wins: int
    losses: int
    open_trades: int
    not_triggered: int
    invalid: int
    win_rate_pct: float
    average_r: float
    expectancy_r: float
    average_win_r: float
    average_loss_r: float
    profit_factor: float | None
    sharpe_like: float | None
    max_drawdown_r: float
    consecutive_losses: int


def _max_drawdown(values: list[float]) -> float:
    peak = 0.0
    equity = 0.0
    max_dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _max_consecutive_losses(results: list[TradeSimulation]) -> int:
    current = 0
    longest = 0
    for result in results:
        if result.status == "loss":
            current += 1
            longest = max(longest, current)
        elif result.status == "win":
            current = 0
    return longest


def calculate_metrics(results: Iterable[TradeSimulation]) -> BacktestMetrics:
    items = list(results)
    triggered = [
        item
        for item in items
        if item.entry_triggered and item.status not in {"invalid", "skipped", "not_triggered"}
    ]
    closed = [item for item in triggered if item.status in {"win", "loss"}]
    wins = [item for item in closed if item.status == "win"]
    losses = [item for item in closed if item.status == "loss"]
    r_values = [float(item.r_multiple) for item in triggered]
    win_r = [float(item.r_multiple) for item in wins]
    loss_r = [abs(float(item.r_multiple)) for item in losses]

    gross_profit = sum(win_r)
    gross_loss = sum(loss_r)
    profit_factor = None if gross_loss == 0 else gross_profit / gross_loss
    sharpe_like = None
    if len(r_values) > 1:
        stdev = pstdev(r_values)
        if stdev > 0:
            sharpe_like = mean(r_values) / stdev * math.sqrt(len(r_values))

    closed_count = len(closed)
    return BacktestMetrics(
        total_signals=len(items),
        triggered_trades=len(triggered),
        wins=len(wins),
        losses=len(losses),
        open_trades=sum(1 for item in triggered if item.status == "open"),
        not_triggered=sum(1 for item in items if item.status == "not_triggered"),
        invalid=sum(1 for item in items if item.status in {"invalid", "skipped"}),
        win_rate_pct=(len(wins) / closed_count * 100.0) if closed_count else 0.0,
        average_r=mean(r_values) if r_values else 0.0,
        expectancy_r=mean(r_values) if r_values else 0.0,
        average_win_r=mean(win_r) if win_r else 0.0,
        average_loss_r=mean(loss_r) if loss_r else 0.0,
        profit_factor=profit_factor,
        sharpe_like=sharpe_like,
        max_drawdown_r=_max_drawdown(r_values),
        consecutive_losses=_max_consecutive_losses(triggered),
    )
