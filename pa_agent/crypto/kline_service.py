"""Crypto K-line persistence, caching, and retrieval service."""
from __future__ import annotations

import json
import logging
import math
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pa_agent.data.base import KlineBar
from pa_agent.data.kline_cache import KlineCacheStore, merge_bars_newest_first

logger = logging.getLogger(__name__)

# Canonical timeframe mappings
TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1D": 86400,
}

TIMEFRAME_OKX_BAR: dict[str, str] = {
    "1m": "1m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
    "1d": "1Dutc",
    "1D": "1Dutc",
}

TIMEFRAME_BINANCE_BAR: dict[str, str] = {
    "1m": "1m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1D": "1d",
}

DEFAULT_CRYPTO_SYMBOLS: tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "XRPUSDT",
)

BASE_PRICES: dict[str, float] = {
    "BTCUSDT": 78040.0,
    "ETHUSDT": 3150.0,
    "SOLUSDT": 185.0,
    "BNBUSDT": 615.0,
    "DOGEUSDT": 0.165,
    "XRPUSDT": 0.582,
}


VOLATILITY_BY_TF: dict[str, float] = {
    "1m": 0.0012,
    "15m": 0.0035,
    "30m": 0.0055,
    "1h": 0.0085,
    "4h": 0.0160,
    "1d": 0.0320,
    "1D": 0.0320,
}


@dataclass(frozen=True)
class CryptoKlineOutput:
    symbol: str
    timeframe: str
    count: int
    source: str
    saved_at: str
    bars: list[dict[str, Any]]


def normalize_crypto_symbol(symbol: str) -> str:
    """Normalize symbol to uppercase alphanumeric (e.g., 'BTC-USDT' -> 'BTCUSDT')."""
    clean = re.sub(r"[^A-Za-z0-9]", "", symbol or "").upper()
    return clean or "BTCUSDT"


def normalize_crypto_timeframe(timeframe: str) -> str:
    """Normalize timeframe string (e.g. '1D' -> '1d')."""
    tf = (timeframe or "1d").strip()
    if tf in {"1D", "1d"}:
        return "1d"
    if tf in TIMEFRAME_SECONDS:
        return tf.lower()
    return "1d"


def _bar_to_chart_dict(bar: KlineBar) -> dict[str, Any]:
    return {
        "time": int(bar.ts_open / 1000),  # in seconds for lightweight-charts
        "open": round(bar.open, 6 if bar.open < 10 else 2),
        "high": round(bar.high, 6 if bar.high < 10 else 2),
        "low": round(bar.low, 6 if bar.low < 10 else 2),
        "close": round(bar.close, 6 if bar.close < 10 else 2),
        "volume": round(bar.volume, 2),
        "amount": round(bar.amount, 2),
    }


def generate_realistic_crypto_bars(
    symbol: str,
    timeframe: str,
    count: int = 1000,
    *,
    end_ts_sec: int | None = None,
) -> list[KlineBar]:
    """Generate high-density, realistic crypto candlestick bars with geometric walk & volatility clustering."""
    norm_symbol = normalize_crypto_symbol(symbol)
    norm_tf = normalize_crypto_timeframe(timeframe)
    interval_sec = TIMEFRAME_SECONDS.get(norm_tf, 86400)
    volatility = VOLATILITY_BY_TF.get(norm_tf, 0.03)

    base_price = BASE_PRICES.get(norm_symbol, 100.0)
    now_sec = end_ts_sec or int(time.time())
    current_aligned_sec = (now_sec // interval_sec) * interval_sec

    # Deterministic seed per symbol and timeframe so reload stays consistent
    seed_val = hash(f"{norm_symbol}_{norm_tf}") & 0x7FFFFFFF
    rng = random.Random(seed_val)

    # Pre-generate price trajectory backwards
    prices = [base_price]
    curr_p = base_price
    for _ in range(count):
        shock = rng.gauss(0, volatility)
        curr_p = max(curr_p * math.exp(-shock), 0.0001)
        prices.append(curr_p)
    prices.reverse()

    bars: list[KlineBar] = []
    prev_close = prices[0]

    for i in range(count):
        bar_time_sec = current_aligned_sec - (count - 1 - i) * interval_sec
        ts_open_ms = float(bar_time_sec * 1000)

        p_target = prices[i + 1]
        open_price = prev_close
        close_price = p_target

        range_vol = abs(open_price) * volatility * rng.uniform(0.5, 1.8)
        high_price = max(open_price, close_price) + range_vol * rng.uniform(0.2, 1.0)
        low_price = min(open_price, close_price) - range_vol * rng.uniform(0.2, 1.0)
        low_price = max(low_price, 0.0001)

        # Realistic volume & turnover
        vol_base = (1000000.0 / base_price) if base_price > 0 else 1000.0
        volume = vol_base * rng.uniform(0.6, 2.5) * (1.0 + (high_price - low_price) / open_price * 10)
        amount = volume * close_price
        pct_chg = ((close_price - open_price) / open_price) * 100.0 if open_price > 0 else 0.0

        bar = KlineBar(
            seq=i + 1,
            ts_open=ts_open_ms,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            amount=amount,
            pct_chg=pct_chg,
            closed=True,
        )
        bars.append(bar)
        prev_close = close_price

    return bars


def fetch_upstream_binance_bars(
    symbol: str,
    timeframe: str,
    limit: int = 1000,
    timeout: float = 3.0,
) -> list[KlineBar]:
    """Attempt to fetch real candles from public Binance Vision / API."""
    norm_symbol = normalize_crypto_symbol(symbol)
    norm_tf = normalize_crypto_timeframe(timeframe)
    interval = TIMEFRAME_BINANCE_BAR.get(norm_tf, "1d")
    fetch_limit = min(max(limit, 10), 1000)

    url = f"https://data-api.binance.vision/api/v3/klines?symbol={norm_symbol}&interval={interval}&limit={fetch_limit}"
    req = Request(url, headers={"User-Agent": "PA-Agent/1.0", "Accept": "application/json"})

    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.warning("Upstream Binance fetch failed for %s (%s): %s", norm_symbol, norm_tf, exc)
        return []

    if not isinstance(data, list) or not data:
        return []

    bars: list[KlineBar] = []
    for idx, row in enumerate(data):
        if not isinstance(row, list) or len(row) < 7:
            continue
        try:
            ts_open = float(row[0])
            open_p = float(row[1])
            high_p = float(row[2])
            low_p = float(row[3])
            close_p = float(row[4])
            vol = float(row[5])
            amt = float(row[7]) if len(row) > 7 else vol * close_p
            pct_chg = ((close_p - open_p) / open_p * 100.0) if open_p > 0 else 0.0
            bars.append(
                KlineBar(
                    seq=idx + 1,
                    ts_open=ts_open,
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    volume=vol,
                    amount=amt,
                    pct_chg=pct_chg,
                    closed=True,
                )
            )
        except (ValueError, TypeError):
            continue

    return bars


def get_or_fetch_crypto_klines(
    kline_cache: KlineCacheStore,
    symbol: str = "BTCUSDT",
    timeframe: str = "1d",
    limit: int = 1000,
    refresh: bool = False,
    allow_upstream: bool = True,
) -> CryptoKlineOutput:
    """Read crypto K-lines from backend disk cache; fetch upstream or generate high-fidelity bars if missing."""
    norm_symbol = normalize_crypto_symbol(symbol)
    norm_tf = normalize_crypto_timeframe(timeframe)
    target_limit = min(max(limit, 10), 3000)

    cached_entry = kline_cache.read("crypto", norm_symbol, norm_tf)

    if (
        cached_entry is not None
        and not refresh
        and len(cached_entry.bars) >= min(target_limit, 300)
    ):
        # Cache hit with sufficient bars
        sorted_bars = sorted(cached_entry.bars, key=lambda b: b.ts_open)
        sliced = sorted_bars[-target_limit:]
        return CryptoKlineOutput(
            symbol=norm_symbol,
            timeframe=norm_tf,
            count=len(sliced),
            source="backend_cache",
            saved_at=cached_entry.saved_at,
            bars=[_bar_to_chart_dict(b) for b in sliced],
        )

    # Need to fetch or generate
    fetched_bars: list[KlineBar] = []
    source_name = "backend_generator"

    if allow_upstream:
        fetched_bars = fetch_upstream_binance_bars(norm_symbol, norm_tf, limit=target_limit)
        if fetched_bars:
            source_name = "binance_upstream"

    if not fetched_bars:
        # Fallback to realistic generation of at least max(target_limit, 1000) bars
        gen_count = max(target_limit, 1000)
        fetched_bars = generate_realistic_crypto_bars(norm_symbol, norm_tf, count=gen_count)
        source_name = "local_generator"

    existing_bars = cached_entry.bars if cached_entry is not None else ()
    merged = merge_bars_newest_first(existing_bars, fetched_bars, max_bars=3000)

    # Write to disk cache
    kline_cache.write(
        source="crypto",
        symbol=norm_symbol,
        timeframe=norm_tf,
        bars=merged,
        max_bars=3000,
    )

    # Read back saved entry
    saved_entry = kline_cache.read("crypto", norm_symbol, norm_tf)
    saved_at = saved_entry.saved_at if saved_entry is not None else datetime.now(timezone.utc).isoformat()

    sorted_bars = sorted(merged, key=lambda b: b.ts_open)
    sliced = sorted_bars[-target_limit:]

    return CryptoKlineOutput(
        symbol=norm_symbol,
        timeframe=norm_tf,
        count=len(sliced),
        source=source_name,
        saved_at=saved_at,
        bars=[_bar_to_chart_dict(b) for b in sliced],
    )


def seed_default_crypto_cache(
    kline_cache: KlineCacheStore,
    count: int = 1000,
    symbols: tuple[str, ...] = DEFAULT_CRYPTO_SYMBOLS,
    timeframes: tuple[str, ...] = ("1m", "15m", "30m", "1h", "4h", "1d"),
    allow_upstream: bool = False,
) -> dict[str, int]:

    """Pre-seed default crypto pairs and timeframes into disk cache for instant large-volume access."""
    results: dict[str, int] = {}
    for sym in symbols:
        for tf in timeframes:
            res = get_or_fetch_crypto_klines(
                kline_cache=kline_cache,
                symbol=sym,
                timeframe=tf,
                limit=count,
                refresh=False,
                allow_upstream=allow_upstream,
            )
            key = f"{sym}_{tf}"
            results[key] = res.count
    return results

