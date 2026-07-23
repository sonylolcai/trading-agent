from __future__ import annotations

import pytest

from pa_agent.backtest.rolling import build_rolling_comparison, build_rolling_summary
from pa_agent.data.base import KlineBar


def _bar(index: int, close: float, *, seq: int = 1) -> KlineBar:
    return KlineBar(
        seq=seq,
        ts_open=float(index * 60_000),
        open=close - 0.4,
        high=close + 0.2,
        low=close - 0.9,
        close=close,
        volume=100.0,
        amount=1000.0,
        closed=True,
    )


def _rising_bars(count: int) -> list[KlineBar]:
    oldest_first = [_bar(i, 100.0 + i, seq=count - i) for i in range(count)]
    return list(reversed(oldest_first))


def _custom_bar(
    index: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    seq: int = 1,
) -> KlineBar:
    return KlineBar(
        seq=seq,
        ts_open=float(index * 60_000),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        amount=1000.0,
        closed=True,
    )


def _choppy_uptrend_bars(count: int) -> list[KlineBar]:
    closes = []
    value = 100.0
    pattern = (0.35, -0.12, 0.34, -0.08, 0.33, 0.18)
    for index in range(count):
        value += pattern[index % len(pattern)]
        closes.append(round(value, 4))
    oldest_first = [
        _custom_bar(
            i,
            open_=close - 0.12,
            high=close + 0.18,
            low=close - 0.72,
            close=close,
            seq=count - i,
        )
        for i, close in enumerate(closes)
    ]
    return list(reversed(oldest_first))


def _rising_bars_with_climactic_breakout(count: int) -> list[KlineBar]:
    oldest_first = []
    for index in range(count):
        close = 100.0 + index
        if index == 24:
            oldest_first.append(
                KlineBar(
                    seq=count - index,
                    ts_open=float(index * 60_000),
                    open=close - 0.4,
                    high=close + 5.0,
                    low=close - 0.9,
                    close=close,
                    volume=500.0,
                    amount=5000.0,
                    closed=True,
                )
            )
        else:
            oldest_first.append(_bar(index, close, seq=count - index))
    return list(reversed(oldest_first))


def _rising_bars_with_volume_confirmation(count: int) -> list[KlineBar]:
    oldest_first = []
    for index in range(count):
        close = 100.0 + index
        if index == 24:
            oldest_first.append(
                KlineBar(
                    seq=count - index,
                    ts_open=float(index * 60_000),
                    open=close - 0.4,
                    high=close + 0.3,
                    low=close - 0.9,
                    close=close,
                    volume=500.0,
                    amount=5000.0,
                    closed=True,
                )
            )
        else:
            oldest_first.append(_bar(index, close, seq=count - index))
    return list(reversed(oldest_first))


def test_rolling_summary_returns_zero_metrics_for_empty_bars() -> None:
    summary = build_rolling_summary(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=[],
        window=100,
    )

    assert summary.to_payload() == {
        "source": "eastmoney",
        "symbol": "000001",
        "timeframe": "1h",
        "window": 100,
        "bar_count": 0,
        "max_holding_bars": None,
        "evaluated_windows": 0,
        "trade_signals": 0,
        "completed_trades": 0,
        "wins": 0,
        "losses": 0,
        "open_trades": 0,
        "not_triggered": 0,
        "invalid": 0,
        "win_rate_pct": 0.0,
        "expectancy_r": 0.0,
        "average_r": 0.0,
        "total_r": 0.0,
        "profit_factor": None,
        "max_drawdown_r": 0.0,
        "skipped_no_setup": 0,
        "skipped_no_followthrough": 0,
        "skipped_volume_caution": 0,
        "volume_caution_reasons": {},
        "risk_profile": "conservative",
        "trades": [],
    }


def test_rolling_summary_generates_real_trade_samples_from_rising_bars() -> None:
    summary = build_rolling_summary(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=_rising_bars(36),
        window=30,
    )
    payload = summary.to_payload()

    assert payload["bar_count"] == 30
    assert payload["evaluated_windows"] > 0
    assert payload["trade_signals"] >= 1
    assert payload["completed_trades"] >= 1
    assert payload["wins"] >= 1
    assert payload["completed_trades"] == payload["wins"] + payload["losses"]
    assert payload["total_r"] > 0
    assert payload["expectancy_r"] == pytest.approx(payload["average_r"])
    assert payload["max_drawdown_r"] >= 0.0
    assert 0 < len(payload["trades"]) <= 20
    assert payload["trades"][0]["direction"] == "做多"
    assert payload["trades"][0]["order_type"] == "突破单"
    assert payload["trades"][0]["r_multiple"] > 0


def test_rolling_summary_scans_until_current_bar_for_exit() -> None:
    oldest_first = [
        _custom_bar(0, open_=99.5, high=100.2, low=99.1, close=100.0),
        _custom_bar(1, open_=100.5, high=101.2, low=100.1, close=101.0),
        _custom_bar(2, open_=101.5, high=102.2, low=101.1, close=102.0),
        _custom_bar(3, open_=102.5, high=103.2, low=102.1, close=103.0),
        _custom_bar(4, open_=103.5, high=104.2, low=103.1, close=104.0),
        _custom_bar(5, open_=104.4, high=105.2, low=104.1, close=105.0),
        *[
            _custom_bar(i, open_=105.1, high=106.4, low=104.7, close=105.6)
            for i in range(6, 14)
        ],
        _custom_bar(14, open_=105.8, high=106.7, low=105.5, close=106.6),
    ]
    newest_first = list(reversed(oldest_first))

    payload = build_rolling_summary(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=newest_first,
        window=len(newest_first),
    ).to_payload()

    first_signal = next(
        trade
        for trade in payload["trades"]
        if trade["signal_index"] == 5 and trade["entry_price"] == pytest.approx(105.2)
    )
    assert first_signal["status"] == "win"
    assert first_signal["bars_held"] > 8


def test_rolling_summary_risk_profile_changes_trade_frequency() -> None:
    bars = _choppy_uptrend_bars(80)

    conservative = build_rolling_summary(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=bars,
        window=80,
        risk_profile="conservative",
    ).to_payload()
    aggressive = build_rolling_summary(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=bars,
        window=80,
        risk_profile="aggressive",
    ).to_payload()

    assert conservative["risk_profile"] == "conservative"
    assert aggressive["risk_profile"] == "aggressive"
    assert aggressive["trade_signals"] > conservative["trade_signals"]


def test_rolling_comparison_returns_price_only_and_volume_assisted_summaries() -> None:
    payload = build_rolling_comparison(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=_rising_bars(36),
        window=30,
    ).to_payload()

    assert payload["source"] == "eastmoney"
    assert payload["symbol"] == "000001"
    assert payload["price_only"]["bar_count"] == 30
    assert payload["volume_assisted"]["bar_count"] == 30
    assert payload["delta"]["trade_signals"] == (
        payload["volume_assisted"]["trade_signals"]
        - payload["price_only"]["trade_signals"]
    )


def test_rolling_comparison_skips_climactic_breakout_only_for_volume_assisted_policy() -> None:
    payload = build_rolling_comparison(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=_rising_bars_with_climactic_breakout(36),
        window=36,
    ).to_payload()

    assert payload["price_only"]["trade_signals"] == payload["volume_assisted"]["trade_signals"] + 1
    assert payload["volume_assisted"]["skipped_volume_caution"] == 1
    assert payload["volume_assisted"]["volume_caution_reasons"] == {
        "high_volume_weak_long_breakout": 1
    }
    assert payload["delta"]["trade_signals"] == -1


def test_rolling_comparison_audits_every_price_signal_by_volume_context() -> None:
    payload = build_rolling_comparison(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=_rising_bars_with_climactic_breakout(36),
        window=36,
    ).to_payload()

    contexts = payload["volume_contexts"]

    assert set(contexts) == {"confirmed", "caution", "neutral", "unavailable"}
    assert sum(context["trade_signals"] for context in contexts.values()) == payload["price_only"]["trade_signals"]
    assert contexts["caution"]["trade_signals"] == 1


def test_rolling_comparison_adds_a_confirmed_volume_candidate_without_changing_price_only() -> None:
    payload = build_rolling_comparison(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=_rising_bars_with_volume_confirmation(36),
        window=36,
    ).to_payload()

    assert payload["price_only"]["trade_signals"] > 1
    assert payload["volume_confirmed"]["trade_signals"] == 1
    assert payload["volume_confirmed"]["trade_signals"] == payload["volume_contexts"]["confirmed"]["trade_signals"]


def test_rolling_comparison_adds_a_time_limited_exit_candidate_for_confirmed_entries() -> None:
    payload = build_rolling_comparison(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=_rising_bars_with_volume_confirmation(36),
        window=36,
    ).to_payload()

    candidate = payload["volume_confirmed_time_exit"]

    assert candidate["max_holding_bars"] == 10
    assert candidate["trade_signals"] == payload["volume_confirmed"]["trade_signals"]
