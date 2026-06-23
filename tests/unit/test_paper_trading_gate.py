from __future__ import annotations

from pa_agent.backtest.paper_gate import evaluate_paper_trading_status
from pa_agent.config.settings import GeneralSettings


def test_paper_trading_gate_locks_until_minimum_trades_are_met() -> None:
    settings = GeneralSettings(
        paper_trading_required=True,
        paper_trading_min_trades=50,
        paper_trading_min_win_rate=40,
        paper_trading_min_expectancy_r=0.0,
    )

    status = evaluate_paper_trading_status(
        settings,
        total_trades=49,
        win_rate_pct=80,
        expectancy_r=0.5,
    )

    assert status.can_emit_live_signals is False
    assert "50" in status.reason


def test_paper_trading_gate_unlocks_when_trade_quality_passes() -> None:
    settings = GeneralSettings(
        paper_trading_required=True,
        paper_trading_min_trades=50,
        paper_trading_min_win_rate=40,
        paper_trading_min_expectancy_r=0.0,
    )

    status = evaluate_paper_trading_status(
        settings,
        total_trades=50,
        win_rate_pct=42,
        expectancy_r=0.05,
    )

    assert status.can_emit_live_signals is True
    assert status.reason == "paper trading requirement satisfied"


def test_symbol_change_requires_symbol_specific_sample() -> None:
    settings = GeneralSettings(
        paper_trading_required=True,
        paper_trading_min_trades=50,
        paper_trading_min_win_rate=40,
        paper_trading_min_expectancy_r=0.0,
        paper_trading_reset_on_symbol_change=True,
        paper_trading_symbol_min_trades=20,
    )

    status = evaluate_paper_trading_status(
        settings,
        total_trades=100,
        win_rate_pct=55,
        expectancy_r=0.2,
        symbol_trades=12,
    )

    assert status.can_emit_live_signals is False
    assert "symbol" in status.reason
