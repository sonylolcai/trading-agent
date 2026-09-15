from __future__ import annotations

from pathlib import Path

from pa_agent.crypto.kline_service import (
    generate_realistic_crypto_bars,
    get_or_fetch_crypto_klines,
    normalize_crypto_symbol,
    normalize_crypto_timeframe,
    seed_default_crypto_cache,
)
from pa_agent.data.kline_cache import KlineCacheStore


def test_symbol_and_timeframe_normalizers() -> None:
    assert normalize_crypto_symbol("btc-usdt") == "BTCUSDT"
    assert normalize_crypto_symbol("ETH_USDT") == "ETHUSDT"
    assert normalize_crypto_symbol("") == "BTCUSDT"

    assert normalize_crypto_timeframe("1D") == "1d"
    assert normalize_crypto_timeframe("1d") == "1d"
    assert normalize_crypto_timeframe("15m") == "15m"
    assert normalize_crypto_timeframe("invalid") == "1d"


def test_generate_realistic_crypto_bars() -> None:
    bars = generate_realistic_crypto_bars("BTCUSDT", "1d", count=100, end_ts_sec=1700000000)
    assert len(bars) == 100
    for i, bar in enumerate(bars):
        assert bar.high >= bar.low
        assert bar.high >= max(bar.open, bar.close)
        assert bar.low <= min(bar.open, bar.close)
        assert bar.volume > 0
        assert bar.ts_open > 0
        if i > 0:
            # Ascending timestamps in generated sequence
            assert bar.ts_open > bars[i - 1].ts_open


def test_kline_service_cache_and_retrieval(tmp_path: Path) -> None:
    cache = KlineCacheStore(tmp_path / "kline_cache")

    # Initial call generates and saves to disk cache
    out1 = get_or_fetch_crypto_klines(
        cache,
        symbol="BTC-USDT",
        timeframe="1d",
        limit=500,
        refresh=False,
        allow_upstream=False,
    )
    assert out1.symbol == "BTCUSDT"
    assert out1.timeframe == "1d"
    assert out1.count == 500
    assert len(out1.bars) == 500
    # Lightweight charts expects strictly ascending time in seconds
    for i in range(1, len(out1.bars)):
        assert out1.bars[i]["time"] > out1.bars[i - 1]["time"]
        assert out1.bars[i]["seq"] == out1.bars[i - 1]["seq"] + 1
    assert out1.bars[0]["seq"] == 1
    assert out1.bars[-1]["seq"] == 500

    # Verify persisted file exists on disk
    entry = cache.read("crypto", "BTCUSDT", "1d")
    assert entry is not None
    assert len(entry.bars) >= 500

    # Second call hits backend_cache
    out2 = get_or_fetch_crypto_klines(
        cache,
        symbol="BTCUSDT",
        timeframe="1d",
        limit=300,
        refresh=False,
        allow_upstream=False,
    )
    assert out2.source == "backend_cache"
    assert out2.count == 300
    assert out2.bars[0]["seq"] == 1
    assert out2.bars[-1]["seq"] == 300


def test_seed_default_crypto_cache(tmp_path: Path) -> None:
    cache = KlineCacheStore(tmp_path / "kline_cache")
    results = seed_default_crypto_cache(
        cache,
        count=150,
        symbols=("BTCUSDT", "ETHUSDT"),
        timeframes=("1h", "1d"),
    )
    assert "BTCUSDT_1h" in results
    assert "ETHUSDT_1d" in results
    assert results["BTCUSDT_1h"] == 150
    assert cache.read("crypto", "BTCUSDT", "1h") is not None
