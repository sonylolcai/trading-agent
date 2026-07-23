from __future__ import annotations

import pytest

from pa_agent.backtest.simulator import simulate_decision
from pa_agent.data.base import KlineBar


def _bar(
    ts: float,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    closed: bool = True,
) -> KlineBar:
    return KlineBar(
        seq=1,
        ts_open=ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        closed=closed,
    )


def test_market_long_hits_target_and_ignores_forming_bar() -> None:
    decision = {
        "order_direction": "做多",
        "order_type": "市价单",
        "entry_price": 100,
        "take_profit_price": 105,
        "stop_loss_price": 95,
    }
    future_bars = [
        _bar(3, open_=100, high=120, low=90, close=101, closed=False),
        _bar(2, open_=101, high=104, low=99, close=103),
        _bar(1, open_=103, high=106, low=102, close=105),
    ]

    result = simulate_decision(decision, future_bars)

    assert result.status == "win"
    assert result.entry_triggered is True
    assert result.ambiguous is False
    assert result.r_multiple == pytest.approx(1.0)


def test_limit_order_not_triggered_is_not_counted_as_trade() -> None:
    decision = {
        "order_direction": "做多",
        "order_type": "限价单",
        "entry_price": 100,
        "take_profit_price": 105,
        "stop_loss_price": 95,
    }
    future_bars = [
        _bar(1, open_=103, high=106, low=101, close=104),
        _bar(2, open_=104, high=107, low=102, close=106),
    ]

    result = simulate_decision(decision, future_bars)

    assert result.status == "not_triggered"
    assert result.entry_triggered is False
    assert result.r_multiple == 0.0


def test_breakout_same_bar_target_and_stop_is_conservative_loss() -> None:
    decision = {
        "order_direction": "做多",
        "order_type": "突破单",
        "entry_price": 101,
        "take_profit_price": 105,
        "stop_loss_price": 97,
    }
    future_bars = [
        _bar(1, open_=100, high=106, low=96, close=104),
    ]

    result = simulate_decision(decision, future_bars)

    assert result.status == "loss"
    assert result.entry_triggered is True
    assert result.ambiguous is True
    assert result.r_multiple == pytest.approx(-1.0)


def test_market_order_can_exit_at_close_when_max_holding_period_is_reached() -> None:
    decision = {
        "order_direction": "做多",
        "order_type": "市价单",
        "entry_price": 100,
        "take_profit_price": 110,
        "stop_loss_price": 95,
    }
    future_bars = [
        _bar(1, open_=100, high=104, low=99, close=103),
        _bar(2, open_=103, high=104, low=101, close=102),
    ]

    result = simulate_decision(decision, future_bars, max_holding_bars=2)

    assert result.status == "win"
    assert result.entry_triggered is True
    assert result.exit_price == pytest.approx(102)
    assert result.bars_held == 2
    assert result.r_multiple == pytest.approx(0.4)
    assert result.reason == "max holding period reached"


def test_invalid_price_geometry_returns_invalid_result() -> None:
    decision = {
        "order_direction": "做多",
        "order_type": "市价单",
        "entry_price": 100,
        "take_profit_price": 98,
        "stop_loss_price": 95,
    }

    result = simulate_decision(decision, [_bar(1, open_=100, high=101, low=99, close=100)])

    assert result.status == "invalid"
    assert result.entry_triggered is False
