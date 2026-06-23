"""Markdown reporting for backtest runs."""
from __future__ import annotations

from pa_agent.backtest.engine import BacktestRun


def render_markdown_report(run: BacktestRun) -> str:
    metrics = run.metrics
    return "\n".join(
        [
            "# PA Agent Backtest Report",
            "",
            f"- total_signals: {metrics.total_signals}",
            f"- triggered_trades: {metrics.triggered_trades}",
            f"- win_rate_pct: {metrics.win_rate_pct:.2f}",
            f"- expectancy_r: {metrics.expectancy_r:.3f}",
            f"- max_drawdown_r: {metrics.max_drawdown_r:.3f}",
            f"- profit_factor: {metrics.profit_factor if metrics.profit_factor is not None else 'N/A'}",
        ]
    )
