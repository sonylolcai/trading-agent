"""Lookahead-safe multi-asset crypto portfolio backtest."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import numpy as np
import pandas as pd

from pa_agent.crypto.okx import OkxClient

UNIVERSE = ("BTC-USDT", "ETH-USDT", "BNB-USDT", "XRP-USDT", "SOL-USDT")
SYMBOLS = tuple(item.split("-", 1)[0] for item in UNIVERSE)
ASSUMED_CORRELATION = 0.65
GROSS_CAPS = {
    "risk_on": 1.0,
    "neutral": 0.5,
    "range": 0.25,
    "risk_off": 0.2,
    "crisis": 0.0,
}
Regime = Literal["risk_on", "neutral", "range", "risk_off", "crisis"]


@dataclass(frozen=True, slots=True)
class CryptoBacktestConfig:
    years: int = 5
    target_volatility: float = 0.15
    cost_bps: float = 10.0
    rebalance_days: int = 7
    strategy_version: Literal["1.0", "2.0"] = "1.0"
    entry_momentum: float = 0.10
    exit_momentum: float = -0.10
    range_efficiency: float = 0.28
    trailing_sigma: float = 2.5
    cooldown_days: int = 7

    def validate(self) -> None:
        if not 2 <= self.years <= 8:
            raise ValueError("years must be between 2 and 8")
        if not 0.05 <= self.target_volatility <= 0.40:
            raise ValueError("target_volatility must be between 0.05 and 0.40")
        if not 0 <= self.cost_bps <= 100:
            raise ValueError("cost_bps must be between 0 and 100")
        if not 1 <= self.rebalance_days <= 30:
            raise ValueError("rebalance_days must be between 1 and 30")
        if self.strategy_version not in {"1.0", "2.0"}:
            raise ValueError("strategy_version must be 1.0 or 2.0")
        if not 0 <= self.entry_momentum <= 0.50:
            raise ValueError("entry_momentum must be between 0 and 0.50")
        if not -0.50 <= self.exit_momentum <= 0:
            raise ValueError("exit_momentum must be between -0.50 and 0")
        if not 0.10 <= self.range_efficiency <= 0.50:
            raise ValueError("range_efficiency must be between 0.10 and 0.50")
        if not 1.0 <= self.trailing_sigma <= 4.0:
            raise ValueError("trailing_sigma must be between 1.0 and 4.0")
        if not 0 <= self.cooldown_days <= 30:
            raise ValueError("cooldown_days must be between 0 and 30")


def _asset_cap(symbol: str) -> float:
    return 0.50 if symbol == "BTC" else 0.25


def _allocate_with_caps(scores: pd.Series, target_gross: float) -> pd.Series:
    weights = pd.Series(0.0, index=SYMBOLS, dtype=float)
    active = scores[scores > 0].sort_values(ascending=False).head(3)
    remaining = float(target_gross)

    while not active.empty and remaining > 1e-9:
        total_score = float(active.sum())
        if total_score <= 1e-9:
            break
        proposed = active / total_score * remaining
        capped = [
            symbol
            for symbol, value in proposed.items()
            if value >= _asset_cap(symbol) - weights[symbol] - 1e-9
        ]
        if not capped:
            weights.loc[active.index] += proposed
            break
        for symbol in capped:
            room = max(0.0, _asset_cap(symbol) - weights[symbol])
            weights[symbol] += room
            remaining -= room
        active = active.drop(index=capped)
    return weights


def _portfolio_volatility(weights: pd.Series, volatilities: pd.Series) -> float:
    variance = 0.0
    for left_index, left in enumerate(SYMBOLS):
        if weights[left] <= 0 or not math.isfinite(float(volatilities[left])):
            continue
        variance += (weights[left] * volatilities[left]) ** 2
        for right in SYMBOLS[left_index + 1 :]:
            if weights[right] <= 0 or not math.isfinite(float(volatilities[right])):
                continue
            variance += (
                2
                * ASSUMED_CORRELATION
                * weights[left]
                * weights[right]
                * volatilities[left]
                * volatilities[right]
            )
    return math.sqrt(max(0.0, variance))


def _regime_at_v1(
    date: pd.Timestamp,
    prices: pd.DataFrame,
    ema100: pd.DataFrame,
    btc_ema50: pd.Series,
    btc_ema200: pd.Series,
    btc_volatility: pd.Series,
) -> Regime:
    btc = float(prices.at[date, "BTC"])
    breadth = int((prices.loc[date] > ema100.loc[date]).sum())
    btc_20d_return = btc / float(prices["BTC"].shift(20).at[date]) - 1.0
    crisis = btc_20d_return <= -0.20 and float(btc_volatility.at[date]) >= 0.80
    if crisis:
        return "crisis"
    trend_up = btc > float(btc_ema200.at[date])
    ema_rising = float(btc_ema50.at[date]) > float(btc_ema50.shift(20).at[date])
    if trend_up and ema_rising and breadth >= 3:
        return "risk_on"
    if trend_up or breadth >= 3:
        return "neutral"
    return "risk_off"


def _build_targets_v1(
    prices: pd.DataFrame,
    *,
    target_volatility: float,
    rebalance_days: int,
) -> tuple[pd.DataFrame, pd.Series]:
    returns = prices.pct_change(fill_method=None)
    daily_volatility = returns.rolling(30).std() * math.sqrt(365)
    history_count = prices.notna().cumsum()
    ema100 = prices.ewm(span=100, adjust=False).mean()
    btc_ema50 = prices["BTC"].ewm(span=50, adjust=False).mean()
    btc_ema200 = prices["BTC"].ewm(span=200, adjust=False).mean()

    momentum = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for lookback, importance in ((20, 0.5), (60, 0.3), (120, 0.2)):
        log_return = np.log(prices / prices.shift(lookback))
        normalizer = returns.rolling(30).std() * math.sqrt(lookback)
        momentum += importance * np.tanh(log_return / normalizer.clip(lower=1e-6))

    targets = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    regimes = pd.Series("risk_off", index=prices.index, dtype=object)
    current = pd.Series(0.0, index=prices.columns, dtype=float)
    last_rebalance: pd.Timestamp | None = None

    for date in prices.index:
        if date < prices.index[200]:
            continue
        regime = _regime_at_v1(
            date,
            prices,
            ema100,
            btc_ema50,
            btc_ema200,
            daily_volatility["BTC"],
        )
        regimes.at[date] = regime
        should_rebalance = (
            last_rebalance is None or (date - last_rebalance).days >= rebalance_days
        )
        if should_rebalance:
            gross_cap = GROSS_CAPS[regime]
            eligible = (
                (history_count.loc[date] >= 200)
                & (prices.loc[date] > ema100.loc[date])
                & (momentum.loc[date] > 0)
            )
            scores = (momentum.loc[date].clip(lower=0) / daily_volatility.loc[date]).where(
                eligible, 0.0
            )
            current = _allocate_with_caps(scores, gross_cap)
            estimated_vol = _portfolio_volatility(current, daily_volatility.loc[date])
            scale = min(1.0, target_volatility / estimated_vol) if estimated_vol > 0 else 0.0
            current *= scale
            last_rebalance = date
        targets.loc[date] = current
    return targets, regimes


def _efficiency_ratio(prices: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    direction = (prices - prices.shift(lookback)).abs()
    path = prices.diff().abs().rolling(lookback).sum()
    return direction / path.replace(0.0, np.nan)


def _regime_at_v2(
    date: pd.Timestamp,
    prices: pd.DataFrame,
    ema100: pd.DataFrame,
    btc_ema50: pd.Series,
    btc_ema200: pd.Series,
    btc_volatility: pd.Series,
    efficiency: pd.DataFrame,
    range_efficiency: float,
) -> Regime:
    btc = float(prices.at[date, "BTC"])
    breadth = int((prices.loc[date] > ema100.loc[date]).sum())
    btc_20d_return = btc / float(prices["BTC"].shift(20).at[date]) - 1.0
    btc_vol = float(btc_volatility.at[date])
    if btc_20d_return <= -0.20 and btc_vol >= 0.80:
        return "crisis"

    ema50_change = float(btc_ema50.at[date] / btc_ema50.shift(20).at[date] - 1.0)
    btc_efficiency = float(efficiency.at[date, "BTC"])
    if btc_efficiency < range_efficiency and abs(ema50_change) < 0.03:
        return "range"

    trend_up = btc > float(btc_ema200.at[date])
    if trend_up and ema50_change > 0 and breadth >= 3:
        return "risk_on"
    if trend_up or breadth >= 3:
        return "neutral"
    return "risk_off"


def _build_targets_v2(
    prices: pd.DataFrame,
    config: CryptoBacktestConfig,
) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    """Build stateful targets with hysteresis, range handling, stops, and cooldowns."""
    returns = prices.pct_change(fill_method=None)
    daily_volatility = returns.rolling(30).std() * math.sqrt(365)
    history_count = prices.notna().cumsum()
    ema100 = prices.ewm(span=100, adjust=False).mean()
    ema100_slope = ema100 / ema100.shift(20) - 1.0
    btc_ema50 = prices["BTC"].ewm(span=50, adjust=False).mean()
    btc_ema200 = prices["BTC"].ewm(span=200, adjust=False).mean()
    efficiency = _efficiency_ratio(prices)

    momentum = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for lookback, importance in ((20, 0.5), (60, 0.3), (120, 0.2)):
        log_return = np.log(prices / prices.shift(lookback))
        normalizer = returns.rolling(30).std() * math.sqrt(lookback)
        momentum += importance * np.tanh(log_return / normalizer.clip(lower=1e-6))

    targets = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    regimes = pd.Series("risk_off", index=prices.index, dtype=object)
    current = pd.Series(0.0, index=prices.columns, dtype=float)
    peaks = pd.Series(np.nan, index=prices.columns, dtype=float)
    cooldown_until: dict[str, pd.Timestamp] = {}
    exit_counts: Counter[str] = Counter()
    entry_count = 0
    regime_deleveraging_count = 0
    last_rebalance: pd.Timestamp | None = None

    for date in prices.index:
        if date < prices.index[200]:
            continue
        regime = _regime_at_v2(
            date,
            prices,
            ema100,
            btc_ema50,
            btc_ema200,
            daily_volatility["BTC"],
            efficiency,
            config.range_efficiency,
        )
        regimes.at[date] = regime

        held_symbols = list(current[current > 1e-9].index)
        for symbol in held_symbols:
            price = float(prices.at[date, symbol])
            if not math.isfinite(price):
                current[symbol] = 0.0
                peaks[symbol] = np.nan
                cooldown_until[symbol] = date + timedelta(days=config.cooldown_days)
                exit_counts["missing_price"] += 1
                continue
            peaks[symbol] = max(float(peaks[symbol]), price)
            annual_vol = float(daily_volatility.at[date, symbol])
            trailing_distance = float(
                np.clip(
                    config.trailing_sigma * annual_vol * math.sqrt(10 / 365),
                    0.10,
                    0.22,
                )
            )
            trailing_break = price <= float(peaks[symbol]) * (1.0 - trailing_distance)
            trend_break = (
                price < float(ema100.at[date, symbol]) * 0.985
                and float(momentum.at[date, symbol]) < 0
            )
            momentum_break = float(momentum.at[date, symbol]) < config.exit_momentum
            reason: str | None = None
            if regime == "crisis":
                reason = "crisis"
            elif trailing_break:
                reason = "trailing_stop"
            elif trend_break:
                reason = "trend_break"
            elif momentum_break:
                reason = "momentum_break"
            if reason is not None:
                current[symbol] = 0.0
                peaks[symbol] = np.nan
                cooldown_until[symbol] = date + timedelta(days=config.cooldown_days)
                exit_counts[reason] += 1

        gross_cap = GROSS_CAPS[regime]
        current_gross = float(current.sum())
        if current_gross > gross_cap + 1e-9:
            current *= gross_cap / current_gross if current_gross > 0 else 0.0
            regime_deleveraging_count += 1

        should_rebalance = (
            last_rebalance is None or (date - last_rebalance).days >= config.rebalance_days
        )
        if should_rebalance:
            held = current > 1e-9
            cooldown_clear = pd.Series(
                {
                    symbol: date >= cooldown_until.get(symbol, date)
                    for symbol in prices.columns
                }
            )
            entry_eligible = (
                (history_count.loc[date] >= 200)
                & (prices.loc[date] > ema100.loc[date] * 1.01)
                & (ema100_slope.loc[date] > 0)
                & (momentum.loc[date] > config.entry_momentum)
                & (efficiency.loc[date] >= config.range_efficiency)
                & cooldown_clear
            )
            if regime in {"range", "crisis"}:
                entry_eligible[:] = False
            hold_eligible = (
                held
                & (history_count.loc[date] >= 200)
                & (prices.loc[date] > ema100.loc[date] * 0.985)
                & (momentum.loc[date] > config.exit_momentum)
            )
            if regime == "range":
                hold_eligible &= (
                    (momentum.loc[date] > 0.05)
                    & (prices.loc[date] > ema100.loc[date])
                )
            if regime == "crisis":
                hold_eligible[:] = False

            eligible = entry_eligible | hold_eligible
            scores = (
                momentum.loc[date].clip(lower=0.02) / daily_volatility.loc[date]
            ).where(eligible, 0.0)
            previous = current.copy()
            current = _allocate_with_caps(scores, gross_cap)
            estimated_vol = _portfolio_volatility(current, daily_volatility.loc[date])
            scale = (
                min(1.0, config.target_volatility / estimated_vol)
                if estimated_vol > 0
                else 0.0
            )
            current *= scale
            for symbol in prices.columns:
                was_held = previous[symbol] > 1e-9
                is_held = current[symbol] > 1e-9
                if is_held and not was_held:
                    peaks[symbol] = float(prices.at[date, symbol])
                    entry_count += 1
                elif not is_held:
                    peaks[symbol] = np.nan
            last_rebalance = date

        targets.loc[date] = current

    diagnostics = {
        "entry_count": entry_count,
        "exit_counts": dict(exit_counts),
        "emergency_exit_count": int(sum(exit_counts.values())),
        "regime_deleveraging_count": regime_deleveraging_count,
        "long_only": True,
        "range_new_entries_allowed": False,
    }
    return targets, regimes, diagnostics


def _metrics(returns: pd.Series, equity: pd.Series) -> dict[str, float | int | None]:
    clean_returns = returns.fillna(0.0)
    if equity.empty:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "annual_volatility": 0.0,
            "sharpe": None,
            "max_drawdown": 0.0,
            "calmar": None,
            "positive_days_pct": 0.0,
        }
    elapsed_years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 365.25)
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1 / elapsed_years) - 1.0)
    annual_volatility = float(clean_returns.std(ddof=0) * math.sqrt(365))
    annual_return = float(clean_returns.mean() * 365)
    sharpe = annual_return / annual_volatility if annual_volatility > 1e-12 else None
    drawdown = equity / equity.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    return {
        "total_return": total_return,
        "cagr": cagr,
        "annual_volatility": annual_volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "calmar": cagr / abs(max_drawdown) if max_drawdown < -1e-12 else None,
        "positive_days_pct": float((clean_returns > 0).mean()),
    }


def _segment_metrics(returns: pd.Series) -> dict[str, Any]:
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    payload = _metrics(returns, equity)
    payload.update(
        {
            "start": returns.index[0].date().isoformat(),
            "end": returns.index[-1].date().isoformat(),
            "days": len(returns),
        }
    )
    return payload


def backtest_crypto_prices(
    closes: pd.DataFrame,
    config: CryptoBacktestConfig,
    *,
    requested_start: pd.Timestamp | None = None,
    include_baseline: bool = True,
) -> dict[str, Any]:
    """Backtest aligned close prices. Signals at t are applied to return t+1."""
    config.validate()
    prices = closes.loc[:, list(SYMBOLS)].sort_index()
    prices = prices.loc[prices["BTC"].notna()]
    if len(prices) < 260:
        raise ValueError("At least 260 aligned daily bars are required")

    if config.strategy_version == "2.0":
        targets, regimes, diagnostics = _build_targets_v2(prices, config)
    else:
        targets, regimes = _build_targets_v1(
            prices,
            target_volatility=config.target_volatility,
            rebalance_days=config.rebalance_days,
        )
        diagnostics = {
            "entry_count": None,
            "exit_counts": {},
            "emergency_exit_count": 0,
            "regime_deleveraging_count": 0,
            "long_only": True,
            "range_new_entries_allowed": None,
        }
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    executed_weights = targets.shift(1).fillna(0.0)
    traded_notional = executed_weights.diff().abs().sum(axis=1)
    if not executed_weights.empty:
        traded_notional.iloc[0] = float(executed_weights.iloc[0].abs().sum())
    gross_returns = (executed_weights * asset_returns).sum(axis=1)
    net_returns = gross_returns - traded_notional * config.cost_bps / 10_000

    start = requested_start or prices.index[200]
    sample_mask = prices.index >= max(start, prices.index[200])
    net_returns = net_returns.loc[sample_mask]
    gross_returns = gross_returns.loc[sample_mask]
    executed_weights = executed_weights.loc[sample_mask]
    traded_notional = traded_notional.loc[sample_mask]
    regimes = regimes.loc[sample_mask]
    asset_returns = asset_returns.loc[sample_mask]
    if len(net_returns) < 30:
        raise ValueError("Requested sample has fewer than 30 usable daily bars")

    equity = (1.0 + net_returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    benchmark_returns = asset_returns["BTC"]
    benchmark_equity = (1.0 + benchmark_returns).cumprod()

    stress_returns = gross_returns - traded_notional * (config.cost_bps * 2) / 10_000
    stress_equity = (1.0 + stress_returns).cumprod()
    split = min(max(int(len(net_returns) * 0.70), 1), len(net_returns) - 1)
    early = net_returns.iloc[:split]
    recent = net_returns.iloc[split:]

    metrics = _metrics(net_returns, equity)
    metrics.update(
        {
            "final_equity": float(equity.iloc[-1]),
            "average_gross_exposure": float(executed_weights.sum(axis=1).mean()),
            "annual_turnover": float(traded_notional.mean() * 365),
            "rebalance_count": int((traded_notional > 1e-9).sum()),
            "total_cost": float((traded_notional * config.cost_bps / 10_000).sum()),
        }
    )
    benchmark_metrics = _metrics(benchmark_returns, benchmark_equity)

    curve = [
        {
            "date": date.date().isoformat(),
            "equity": float(equity.at[date]),
            "benchmark": float(benchmark_equity.at[date]),
            "drawdown": float(drawdown.at[date]),
            "gross_exposure": float(executed_weights.loc[date].sum()),
        }
        for date in equity.index
    ]
    annual_returns = {
        str(year): float((1.0 + group).prod() - 1.0)
        for year, group in net_returns.groupby(net_returns.index.year)
    }
    latest_weights = {
        symbol: float(weight)
        for symbol, weight in executed_weights.iloc[-1].items()
        if weight > 1e-6
    }
    regime_counts = {str(key): int(value) for key, value in regimes.value_counts().items()}

    result = {
        "strategy": {
            "name": (
                "Top-5 Regime Momentum State Machine"
                if config.strategy_version == "2.0"
                else "Top-5 Regime Momentum"
            ),
            "version": config.strategy_version,
            "execution": "close signal at t, held from t+1",
            "funding_history_included": False,
            "shorting_enabled": False,
        },
        "config": {
            "years": config.years,
            "target_volatility": config.target_volatility,
            "cost_bps": config.cost_bps,
            "rebalance_days": config.rebalance_days,
            "strategy_version": config.strategy_version,
            "entry_momentum": config.entry_momentum,
            "exit_momentum": config.exit_momentum,
            "range_efficiency": config.range_efficiency,
            "trailing_sigma": config.trailing_sigma,
            "cooldown_days": config.cooldown_days,
            "assets": list(SYMBOLS),
        },
        "sample": {
            "start": equity.index[0].date().isoformat(),
            "end": equity.index[-1].date().isoformat(),
            "days": len(equity),
        },
        "metrics": metrics,
        "benchmark": {"name": "BTC buy and hold", **benchmark_metrics},
        "validation": {
            "early_70_pct": _segment_metrics(early),
            "recent_30_pct": _segment_metrics(recent),
        },
        "stress": {
            "name": "2x trading friction",
            "cost_bps": config.cost_bps * 2,
            **_metrics(stress_returns, stress_equity),
        },
        "latest": {
            "date": equity.index[-1].date().isoformat(),
            "regime": str(regimes.iloc[-1]),
            "weights": latest_weights,
            "cash_weight": float(1.0 - executed_weights.iloc[-1].sum()),
        },
        "annual_returns": annual_returns,
        "regime_days": regime_counts,
        "diagnostics": diagnostics,
        "curve": curve,
    }
    if config.strategy_version == "2.0" and include_baseline:
        baseline = backtest_crypto_prices(
            closes,
            replace(config, strategy_version="1.0"),
            requested_start=requested_start,
            include_baseline=False,
        )
        result["baseline_v1"] = {
            "metrics": baseline["metrics"],
            "recent_30_pct": baseline["validation"]["recent_30_pct"],
            "latest": baseline["latest"],
        }
    return result


def run_okx_crypto_backtest(
    config: CryptoBacktestConfig,
    *,
    client: OkxClient | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch OKX daily candles and run the portfolio backtest."""
    config.validate()
    closes, source, requested_start = fetch_okx_crypto_closes(
        config,
        client=client,
        now=now,
    )
    result = backtest_crypto_prices(
        closes,
        config,
        requested_start=requested_start,
    )
    result["source"] = source
    return result


def fetch_okx_crypto_closes(
    config: CryptoBacktestConfig,
    *,
    client: OkxClient | None = None,
    now: datetime | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], pd.Timestamp]:
    """Fetch the shared OKX price panel once for repeated robustness runs."""
    config.validate()
    active_client = client or OkxClient()
    end = now or datetime.now(UTC)
    requested_start = end - timedelta(days=round(config.years * 365.25))
    fetch_start = requested_start - timedelta(days=420)
    frames: list[pd.Series] = []
    bar_counts: dict[str, int] = {}

    for instrument_id, symbol in zip(UNIVERSE, SYMBOLS, strict=True):
        candles = active_client.history_candles(
            instrument_id,
            start_ms=int(fetch_start.timestamp() * 1000),
        )
        if not candles:
            raise ValueError(f"OKX returned no closed daily candles for {instrument_id}")
        index = pd.to_datetime([item.ts_ms for item in candles], unit="ms", utc=True)
        series = pd.Series([item.close for item in candles], index=index, name=symbol)
        frames.append(series[~series.index.duplicated(keep="last")])
        bar_counts[symbol] = len(series)

    closes = pd.concat(frames, axis=1, join="outer").sort_index()
    source = {
        "provider": "OKX",
        "endpoint": "/api/v5/market/history-candles",
        "bar": "1Dutc",
        "closed_candles_only": True,
        "raw_bar_counts": bar_counts,
        "calendar_bar_count": len(closes),
        "common_bar_count": int(closes.notna().all(axis=1).sum()),
        "fetched_at": end.isoformat(),
    }
    return closes, source, pd.Timestamp(requested_start)
