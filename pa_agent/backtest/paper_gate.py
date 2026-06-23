"""Paper-trading unlock checks for future live-signal gating."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PaperTradingStatus:
    can_emit_live_signals: bool
    reason: str
    required_trades: int
    observed_trades: int
    win_rate_pct: float
    expectancy_r: float


def evaluate_paper_trading_status(
    settings: Any,
    *,
    total_trades: int,
    win_rate_pct: float,
    expectancy_r: float,
    symbol_trades: int | None = None,
) -> PaperTradingStatus:
    """Return whether live signal mode should be considered unlocked."""
    required = int(getattr(settings, "paper_trading_min_trades", 50) or 0)
    min_win_rate = float(getattr(settings, "paper_trading_min_win_rate", 40) or 0)
    min_expectancy = float(getattr(settings, "paper_trading_min_expectancy_r", 0.0) or 0.0)
    required_enabled = bool(getattr(settings, "paper_trading_required", True))
    observed = max(0, int(total_trades or 0))
    win_rate = float(win_rate_pct or 0.0)
    expectancy = float(expectancy_r or 0.0)

    if not required_enabled:
        return PaperTradingStatus(
            can_emit_live_signals=True,
            reason="paper trading requirement disabled",
            required_trades=0,
            observed_trades=observed,
            win_rate_pct=win_rate,
            expectancy_r=expectancy,
        )

    if observed < required:
        return PaperTradingStatus(
            can_emit_live_signals=False,
            reason=f"paper trading requires at least {required} completed trades",
            required_trades=required,
            observed_trades=observed,
            win_rate_pct=win_rate,
            expectancy_r=expectancy,
        )

    if win_rate < min_win_rate:
        return PaperTradingStatus(
            can_emit_live_signals=False,
            reason=f"paper trading win rate {win_rate:.1f}% is below {min_win_rate:.1f}%",
            required_trades=required,
            observed_trades=observed,
            win_rate_pct=win_rate,
            expectancy_r=expectancy,
        )

    if expectancy < min_expectancy:
        return PaperTradingStatus(
            can_emit_live_signals=False,
            reason=f"paper trading expectancy {expectancy:.3f}R is below {min_expectancy:.3f}R",
            required_trades=required,
            observed_trades=observed,
            win_rate_pct=win_rate,
            expectancy_r=expectancy,
        )

    if bool(getattr(settings, "paper_trading_reset_on_symbol_change", True)):
        symbol_required = int(getattr(settings, "paper_trading_symbol_min_trades", 20) or 0)
        if symbol_trades is not None and int(symbol_trades) < symbol_required:
            return PaperTradingStatus(
                can_emit_live_signals=False,
                reason=f"symbol paper trading requires at least {symbol_required} completed trades",
                required_trades=symbol_required,
                observed_trades=max(0, int(symbol_trades)),
                win_rate_pct=win_rate,
                expectancy_r=expectancy,
            )

    return PaperTradingStatus(
        can_emit_live_signals=True,
        reason="paper trading requirement satisfied",
        required_trades=required,
        observed_trades=observed,
        win_rate_pct=win_rate,
        expectancy_r=expectancy,
    )
