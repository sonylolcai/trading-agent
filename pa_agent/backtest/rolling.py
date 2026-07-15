"""Deterministic rolling backtest summaries for the current K-line window.

This is a lightweight rolling proxy, not an LLM bar-by-bar replay. It scans
cached closed bars, generates conservative momentum breakout plans, and then
uses the shared trade simulator/metrics stack to produce explainable stats.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from pa_agent.backtest.metrics import BacktestMetrics, calculate_metrics
from pa_agent.backtest.simulator import TradeSimulation, simulate_decision
from pa_agent.data.base import KlineBar

LOOKBACK_BARS = 5
TARGET_R = 1.2
RECENT_TRADE_LIMIT = 20


@dataclass(frozen=True)
class RollingRiskPreset:
    profile: str
    min_directional_moves: int
    min_net_range_multiple: float
    require_followthrough: bool
    risk_range_multiplier: float
    target_r: float


ROLLING_RISK_PRESETS: dict[str, RollingRiskPreset] = {
    "conservative": RollingRiskPreset(
        profile="conservative",
        min_directional_moves=LOOKBACK_BARS - 1,
        min_net_range_multiple=0.5,
        require_followthrough=True,
        risk_range_multiplier=0.75,
        target_r=TARGET_R,
    ),
    "balanced": RollingRiskPreset(
        profile="balanced",
        min_directional_moves=3,
        min_net_range_multiple=0.35,
        require_followthrough=True,
        risk_range_multiplier=0.65,
        target_r=1.25,
    ),
    "aggressive": RollingRiskPreset(
        profile="aggressive",
        min_directional_moves=2,
        min_net_range_multiple=0.2,
        require_followthrough=False,
        risk_range_multiplier=0.55,
        target_r=1.35,
    ),
    "extreme_aggressive": RollingRiskPreset(
        profile="extreme_aggressive",
        min_directional_moves=2,
        min_net_range_multiple=0.1,
        require_followthrough=False,
        risk_range_multiplier=0.45,
        target_r=1.5,
    ),
}


@dataclass(frozen=True)
class RollingTrade:
    signal_index: int
    signal_seq: int
    entry_index: int | None
    entry_seq: int | None
    exit_index: int | None
    exit_seq: int | None
    order_type: str
    direction: str
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    status: str
    r_multiple: float
    bars_held: int
    reason: str

    def to_payload(self) -> dict[str, object]:
        return {
            "signal_index": self.signal_index,
            "signal_seq": self.signal_seq,
            "entry_index": self.entry_index,
            "entry_seq": self.entry_seq,
            "exit_index": self.exit_index,
            "exit_seq": self.exit_seq,
            "order_type": self.order_type,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "status": self.status,
            "r_multiple": self.r_multiple,
            "bars_held": self.bars_held,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RollingBacktestSummary:
    source: str
    symbol: str
    timeframe: str
    risk_profile: str
    window: int
    bar_count: int
    evaluated_windows: int
    metrics: BacktestMetrics
    total_r: float
    skipped_no_setup: int
    skipped_no_followthrough: int
    trades: tuple[RollingTrade, ...]

    def to_payload(self) -> dict[str, object]:
        completed = self.metrics.wins + self.metrics.losses
        return {
            "source": self.source,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "risk_profile": self.risk_profile,
            "window": self.window,
            "bar_count": self.bar_count,
            "evaluated_windows": self.evaluated_windows,
            "trade_signals": self.metrics.total_signals,
            "completed_trades": completed,
            "wins": self.metrics.wins,
            "losses": self.metrics.losses,
            "open_trades": self.metrics.open_trades,
            "not_triggered": self.metrics.not_triggered,
            "invalid": self.metrics.invalid,
            "win_rate_pct": self.metrics.win_rate_pct,
            "expectancy_r": self.metrics.expectancy_r,
            "average_r": self.metrics.average_r,
            "total_r": self.total_r,
            "profit_factor": self.metrics.profit_factor,
            "max_drawdown_r": self.metrics.max_drawdown_r,
            "skipped_no_setup": self.skipped_no_setup,
            "skipped_no_followthrough": self.skipped_no_followthrough,
            "trades": [trade.to_payload() for trade in self.trades],
        }


def _closed_oldest_first(bars: Iterable[KlineBar], window: int) -> list[KlineBar]:
    closed = [bar for bar in bars if bool(getattr(bar, "closed", True))]
    closed.sort(key=lambda bar: float(getattr(bar, "ts_open", 0.0) or 0.0))
    return closed[-max(0, window) :]


def _average_range(bars: Iterable[KlineBar]) -> float:
    ranges = [max(0.0, float(bar.high) - float(bar.low)) for bar in bars]
    return mean(ranges) if ranges else 0.0


def _resolve_risk_preset(risk_profile: str | None) -> RollingRiskPreset:
    try:
        from pa_agent.ai.decision_stance import normalize_stance

        key = normalize_stance(risk_profile)
    except Exception:
        key = "conservative"
    return ROLLING_RISK_PRESETS.get(key, ROLLING_RISK_PRESETS["conservative"])


def _momentum_direction(context: list[KlineBar], preset: RollingRiskPreset) -> str | None:
    closes = [float(bar.close) for bar in context]
    if len(closes) < LOOKBACK_BARS + 1:
        return None

    up_moves = sum(1 for left, right in zip(closes, closes[1:], strict=False) if right > left)
    down_moves = sum(1 for left, right in zip(closes, closes[1:], strict=False) if right < left)
    net_change = closes[-1] - closes[0]
    avg_range = _average_range(context)
    if avg_range <= 0:
        return None
    if (
        up_moves >= preset.min_directional_moves
        and net_change > avg_range * preset.min_net_range_multiple
    ):
        return "long"
    if (
        down_moves >= preset.min_directional_moves
        and -net_change > avg_range * preset.min_net_range_multiple
    ):
        return "short"
    return None


def _has_followthrough(direction: str, prior: list[KlineBar], signal: KlineBar) -> bool:
    if direction == "long":
        prior_high = max(float(bar.high) for bar in prior)
        return float(signal.close) > float(signal.open) and float(signal.close) >= prior_high
    prior_low = min(float(bar.low) for bar in prior)
    return float(signal.close) < float(signal.open) and float(signal.close) <= prior_low


def _breakout_decision(
    direction: str,
    signal: KlineBar,
    avg_range: float,
    preset: RollingRiskPreset,
) -> dict[str, object]:
    if direction == "long":
        entry = float(signal.high)
        risk = max(entry - float(signal.low), avg_range * preset.risk_range_multiplier)
        return {
            "order_direction": "做多",
            "order_type": "突破单",
            "entry_price": entry,
            "stop_loss_price": entry - risk,
            "take_profit_price": entry + risk * preset.target_r,
        }

    entry = float(signal.low)
    risk = max(float(signal.high) - entry, avg_range * preset.risk_range_multiplier)
    return {
        "order_direction": "做空",
        "order_type": "突破单",
        "entry_price": entry,
        "stop_loss_price": entry + risk,
        "take_profit_price": entry - risk * preset.target_r,
    }


def _entry_touched(decision: dict[str, object], bar: KlineBar) -> bool:
    entry = float(decision["entry_price"])
    direction = str(decision["order_direction"])
    if direction == "做多":
        return float(bar.high) >= entry
    return float(bar.low) <= entry


def _locate_entry_index(
    decision: dict[str, object],
    future_bars: list[KlineBar],
) -> int | None:
    for idx, bar in enumerate(future_bars):
        if _entry_touched(decision, bar):
            return idx
    return None


def _rolling_trade(
    *,
    decision: dict[str, object],
    result: TradeSimulation,
    bars: list[KlineBar],
    signal_index: int,
    future_bars: list[KlineBar],
) -> RollingTrade:
    entry_offset = _locate_entry_index(decision, future_bars) if result.entry_triggered else None
    entry_index = signal_index + 1 + entry_offset if entry_offset is not None else None
    exit_index = None
    if entry_index is not None and result.bars_held > 0:
        exit_index = min(entry_index + result.bars_held - 1, len(bars) - 1)

    signal = bars[signal_index]
    entry_bar = bars[entry_index] if entry_index is not None else None
    exit_bar = bars[exit_index] if exit_index is not None else None
    return RollingTrade(
        signal_index=signal_index,
        signal_seq=int(signal.seq),
        entry_index=entry_index,
        entry_seq=None if entry_bar is None else int(entry_bar.seq),
        exit_index=exit_index,
        exit_seq=None if exit_bar is None else int(exit_bar.seq),
        order_type=str(decision["order_type"]),
        direction=str(decision["order_direction"]),
        entry_price=float(decision["entry_price"]),
        stop_loss_price=float(decision["stop_loss_price"]),
        take_profit_price=float(decision["take_profit_price"]),
        status=result.status,
        r_multiple=float(result.r_multiple),
        bars_held=result.bars_held,
        reason=result.reason,
    )


def _empty_summary(
    *,
    source: str,
    symbol: str,
    timeframe: str,
    risk_profile: str,
    window: int,
    bar_count: int,
    evaluated_windows: int = 0,
    skipped_no_setup: int = 0,
    skipped_no_followthrough: int = 0,
) -> RollingBacktestSummary:
    return RollingBacktestSummary(
        source=source,
        symbol=symbol,
        timeframe=timeframe,
        risk_profile=risk_profile,
        window=window,
        bar_count=bar_count,
        evaluated_windows=evaluated_windows,
        metrics=calculate_metrics(()),
        total_r=0.0,
        skipped_no_setup=skipped_no_setup,
        skipped_no_followthrough=skipped_no_followthrough,
        trades=(),
    )


def build_rolling_summary(
    *,
    source: str,
    symbol: str,
    timeframe: str,
    bars: Iterable[KlineBar],
    window: int = 100,
    risk_profile: str | None = None,
) -> RollingBacktestSummary:
    """Build a rolling backtest summary from cached K-lines.

    Bars may be newest-first or unordered; only closed bars in the most recent
    ``window`` are used. The generated plans are deterministic proxy signals
    intended for a dashboard summary, not full historical LLM re-evaluation.
    """
    normalized_window = max(1, int(window))
    preset = _resolve_risk_preset(risk_profile)
    window_bars = _closed_oldest_first(bars, normalized_window)
    if len(window_bars) <= LOOKBACK_BARS + 1:
        return _empty_summary(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            risk_profile=preset.profile,
            window=normalized_window,
            bar_count=len(window_bars),
        )

    results: list[TradeSimulation] = []
    trades: list[RollingTrade] = []
    evaluated_windows = 0
    skipped_no_setup = 0
    skipped_no_followthrough = 0

    for signal_index in range(LOOKBACK_BARS, len(window_bars) - 1):
        prior = window_bars[signal_index - LOOKBACK_BARS : signal_index]
        signal = window_bars[signal_index]
        context = [*prior, signal]
        evaluated_windows += 1

        direction = _momentum_direction(context, preset)
        if direction is None:
            skipped_no_setup += 1
            continue
        if preset.require_followthrough and not _has_followthrough(direction, prior, signal):
            skipped_no_followthrough += 1
            continue

        avg_range = _average_range(context)
        decision = _breakout_decision(direction, signal, avg_range, preset)
        future_bars = window_bars[signal_index + 1 :]
        result = simulate_decision(decision, future_bars)
        results.append(result)
        trades.append(
            _rolling_trade(
                decision=decision,
                result=result,
                bars=window_bars,
                signal_index=signal_index,
                future_bars=future_bars,
            )
        )

    if not results:
        return _empty_summary(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            risk_profile=preset.profile,
            window=normalized_window,
            bar_count=len(window_bars),
            evaluated_windows=evaluated_windows,
            skipped_no_setup=skipped_no_setup,
            skipped_no_followthrough=skipped_no_followthrough,
        )

    metrics = calculate_metrics(results)
    triggered_r = [
        float(result.r_multiple)
        for result in results
        if result.entry_triggered and result.status not in {"invalid", "skipped", "not_triggered"}
    ]
    recent_trades = tuple(reversed(trades[-RECENT_TRADE_LIMIT:]))
    return RollingBacktestSummary(
        source=source,
        symbol=symbol,
        timeframe=timeframe,
        risk_profile=preset.profile,
        window=normalized_window,
        bar_count=len(window_bars),
        evaluated_windows=evaluated_windows,
        metrics=metrics,
        total_r=sum(triggered_r),
        skipped_no_setup=skipped_no_setup,
        skipped_no_followthrough=skipped_no_followthrough,
        trades=recent_trades,
    )
