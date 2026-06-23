"""Conservative trade simulator for Stage 2 decisions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pa_agent.data.base import KlineBar
from pa_agent.util.trade_metrics import compute_risk_reward, is_long_direction

TRADE_ORDER_TYPES = {"限价单", "突破单", "市价单"}


@dataclass(frozen=True)
class TradeSimulation:
    """Outcome of simulating one Stage 2 trade plan."""

    status: str
    r_multiple: float
    entry_triggered: bool
    exit_price: float | None
    bars_held: int
    reason: str
    ambiguous: bool = False


def _decision_dict(decision_or_stage2: dict[str, Any]) -> dict[str, Any]:
    nested = decision_or_stage2.get("decision")
    if isinstance(nested, dict):
        return nested
    return decision_or_stage2


def _closed_oldest_first(bars: Iterable[KlineBar]) -> list[KlineBar]:
    closed = [bar for bar in bars if bool(getattr(bar, "closed", True))]
    return sorted(closed, key=lambda bar: float(getattr(bar, "ts_open", 0.0) or 0.0))


def _as_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_long(decision: dict[str, Any]) -> bool | None:
    long = is_long_direction(decision.get("order_direction"))
    if long is not None:
        return long
    entry = _as_float(decision.get("entry_price"))
    target = _as_float(decision.get("take_profit_price"))
    stop = _as_float(decision.get("stop_loss_price"))
    if entry is None or target is None or stop is None:
        return None
    if stop < entry < target:
        return True
    if target < entry < stop:
        return False
    return None


def _entry_triggered(order_type: str, long: bool, entry: float, bar: KlineBar) -> bool:
    if order_type == "市价单":
        return True
    if order_type == "限价单":
        return float(bar.low) <= entry if long else float(bar.high) >= entry
    if order_type == "突破单":
        return float(bar.high) >= entry if long else float(bar.low) <= entry
    return False


def _exit_hit(
    *,
    long: bool,
    target: float,
    stop: float,
    bar: KlineBar,
) -> tuple[str | None, float | None, bool]:
    if long:
        hit_stop = float(bar.low) <= stop
        hit_target = float(bar.high) >= target
    else:
        hit_stop = float(bar.high) >= stop
        hit_target = float(bar.low) <= target

    if hit_stop and hit_target:
        return "loss", stop, True
    if hit_stop:
        return "loss", stop, False
    if hit_target:
        return "win", target, False
    return None, None, False


def _open_r_multiple(*, long: bool, entry: float, risk: float, close: float) -> float:
    if risk <= 0:
        return 0.0
    return (close - entry) / risk if long else (entry - close) / risk


def simulate_decision(
    decision_or_stage2: dict[str, Any],
    future_bars: Iterable[KlineBar],
) -> TradeSimulation:
    """Simulate one Stage 2 order against future K-lines.

    The simulator is deliberately conservative. If the same bar touches both
    stop and target, the trade is marked as a loss and ``ambiguous=True``.
    """
    decision = _decision_dict(decision_or_stage2)
    order_type = str(decision.get("order_type") or "").strip()
    if order_type not in TRADE_ORDER_TYPES:
        return TradeSimulation(
            status="skipped",
            r_multiple=0.0,
            entry_triggered=False,
            exit_price=None,
            bars_held=0,
            reason="no trade order",
        )

    entry = _as_float(decision.get("entry_price"))
    target = _as_float(decision.get("take_profit_price"))
    stop = _as_float(decision.get("stop_loss_price"))
    long = _is_long(decision)
    rr = compute_risk_reward(entry, target, stop, decision.get("order_direction"))
    if entry is None or target is None or stop is None or long is None or rr is None:
        return TradeSimulation(
            status="invalid",
            r_multiple=0.0,
            entry_triggered=False,
            exit_price=None,
            bars_held=0,
            reason="invalid entry/target/stop geometry",
        )

    risk = float(rr["risk"])
    reward = float(rr["reward"])
    win_r = reward / risk
    bars = _closed_oldest_first(future_bars)

    if order_type == "市价单":
        entry_index = 0
        entry_triggered = True
    else:
        entry_index = -1
        entry_triggered = False
        for idx, bar in enumerate(bars):
            if _entry_triggered(order_type, long, entry, bar):
                entry_index = idx
                entry_triggered = True
                break

    if not entry_triggered:
        return TradeSimulation(
            status="not_triggered",
            r_multiple=0.0,
            entry_triggered=False,
            exit_price=None,
            bars_held=0,
            reason="entry was not touched",
        )

    if not bars:
        return TradeSimulation(
            status="open",
            r_multiple=0.0,
            entry_triggered=True,
            exit_price=None,
            bars_held=0,
            reason="no closed future bars",
        )

    bars_to_scan = bars[entry_index:]
    for held, bar in enumerate(bars_to_scan, 1):
        status, exit_price, ambiguous = _exit_hit(
            long=long,
            target=target,
            stop=stop,
            bar=bar,
        )
        if status == "win":
            return TradeSimulation(
                status="win",
                r_multiple=win_r,
                entry_triggered=True,
                exit_price=exit_price,
                bars_held=held,
                reason="target hit",
                ambiguous=ambiguous,
            )
        if status == "loss":
            return TradeSimulation(
                status="loss",
                r_multiple=-1.0,
                entry_triggered=True,
                exit_price=exit_price,
                bars_held=held,
                reason="stop hit" if not ambiguous else "target and stop hit in same bar",
                ambiguous=ambiguous,
            )

    last = bars_to_scan[-1]
    return TradeSimulation(
        status="open",
        r_multiple=_open_r_multiple(
            long=long,
            entry=entry,
            risk=risk,
            close=float(last.close),
        ),
        entry_triggered=True,
        exit_price=float(last.close),
        bars_held=len(bars_to_scan),
        reason="still open after supplied bars",
    )
