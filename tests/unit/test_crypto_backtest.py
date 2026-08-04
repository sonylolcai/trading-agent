from __future__ import annotations

import numpy as np
import pandas as pd

from pa_agent.crypto.backtest import SYMBOLS, CryptoBacktestConfig, backtest_crypto_prices


def _sample_prices(days: int = 1100) -> pd.DataFrame:
    rng = np.random.default_rng(17)
    index = pd.date_range("2022-01-01", periods=days, freq="D", tz="UTC")
    data = {}
    for offset, symbol in enumerate(SYMBOLS):
        cycle = np.sin(np.arange(days) / (40 + offset * 7)) * 0.006
        noise = rng.normal(0, 0.012 + offset * 0.002, days)
        drift = 0.0007 - offset * 0.00005
        returns = drift + cycle + noise
        data[symbol] = 100 * np.exp(np.cumsum(returns))
    return pd.DataFrame(data, index=index)


def test_crypto_backtest_returns_drawdown_validation_and_benchmark() -> None:
    result = backtest_crypto_prices(
        _sample_prices(),
        CryptoBacktestConfig(
            years=3,
            target_volatility=0.15,
            cost_bps=10,
            rebalance_days=7,
            strategy_version="2.0",
        ),
    )

    assert result["sample"]["days"] == 900
    assert result["metrics"]["max_drawdown"] <= 0
    assert result["metrics"]["rebalance_count"] > 0
    assert result["benchmark"]["name"] == "BTC buy and hold"
    assert result["validation"]["early_70_pct"]["days"] == 630
    assert result["validation"]["recent_30_pct"]["days"] == 270
    assert len(result["curve"]) == 900
    assert set(result["latest"]["weights"]).issubset(set(SYMBOLS))
    assert sum(result["latest"]["weights"].values()) <= 1.000001
    assert result["strategy"]["version"] == "2.0"
    assert result["strategy"]["shorting_enabled"] is False
    assert result["diagnostics"]["long_only"] is True
    assert result["diagnostics"]["entry_count"] > 0
    assert result["diagnostics"]["emergency_exit_count"] > 0
    assert "baseline_v1" in result
    assert all(point["gross_exposure"] >= 0 for point in result["curve"])


def test_double_friction_cannot_improve_terminal_return() -> None:
    result = backtest_crypto_prices(
        _sample_prices(),
        CryptoBacktestConfig(years=3, target_volatility=0.15, cost_bps=15, rebalance_days=7),
    )

    assert result["stress"]["total_return"] <= result["metrics"]["total_return"] + 1e-12


def test_last_close_cannot_change_already_executed_weights() -> None:
    prices = _sample_prices()
    baseline = backtest_crypto_prices(prices, CryptoBacktestConfig(years=3))
    shocked = prices.copy()
    shocked.iloc[-1] = shocked.iloc[-1] * np.array([0.55, 1.45, 0.70, 1.30, 0.60])

    result = backtest_crypto_prices(shocked, CryptoBacktestConfig(years=3))

    assert result["latest"]["weights"] == baseline["latest"]["weights"]


def test_late_listing_does_not_truncate_the_portfolio_sample() -> None:
    prices = _sample_prices()
    prices.loc[prices.index[:500], "BNB"] = np.nan

    result = backtest_crypto_prices(prices, CryptoBacktestConfig(years=3))

    assert result["sample"]["days"] == 900


def test_flat_choppy_market_is_classified_as_range_without_new_range_entries() -> None:
    days = 700
    index = pd.date_range("2022-01-01", periods=days, freq="D", tz="UTC")
    oscillation = np.sin(np.arange(days) / 3) * 0.008
    prices = pd.DataFrame(
        {
            symbol: 100 * np.exp(np.cumsum(oscillation * (1 + offset * 0.05)))
            for offset, symbol in enumerate(SYMBOLS)
        },
        index=index,
    )

    result = backtest_crypto_prices(
        prices,
        CryptoBacktestConfig(years=2, strategy_version="2.0"),
    )

    assert result["regime_days"].get("range", 0) > 100
    assert result["diagnostics"]["range_new_entries_allowed"] is False


def test_v1_remains_available_as_an_explicit_baseline() -> None:
    result = backtest_crypto_prices(
        _sample_prices(),
        CryptoBacktestConfig(years=3, strategy_version="1.0"),
    )

    assert result["strategy"]["version"] == "1.0"
    assert "baseline_v1" not in result
    assert result["diagnostics"]["emergency_exit_count"] == 0


def test_invalid_sample_is_rejected() -> None:
    prices = _sample_prices(200)

    try:
        backtest_crypto_prices(prices, CryptoBacktestConfig())
    except ValueError as exc:
        assert "260" in str(exc)
    else:
        raise AssertionError("Expected a short sample to be rejected")
