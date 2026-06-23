"""Backtesting and data-feedback helpers for PA Agent."""
from __future__ import annotations

from pa_agent.backtest.engine import BacktestCase, BacktestEngine, BacktestRun
from pa_agent.backtest.metrics import BacktestMetrics, calculate_metrics
from pa_agent.backtest.paper_gate import PaperTradingStatus, evaluate_paper_trading_status
from pa_agent.backtest.record_replay import (
    RecordReplaySummary,
    format_record_replay_summary,
    rebuild_setup_stats_from_records,
)
from pa_agent.backtest.setup_key import SetupKey, build_setup_key
from pa_agent.backtest.simulator import TradeSimulation, simulate_decision
from pa_agent.backtest.stats_store import SetupStats, SetupStatsLedger

__all__ = [
    "BacktestCase",
    "BacktestEngine",
    "BacktestMetrics",
    "BacktestRun",
    "PaperTradingStatus",
    "RecordReplaySummary",
    "SetupKey",
    "SetupStats",
    "SetupStatsLedger",
    "TradeSimulation",
    "build_setup_key",
    "calculate_metrics",
    "evaluate_paper_trading_status",
    "format_record_replay_summary",
    "rebuild_setup_stats_from_records",
    "simulate_decision",
]
