import json

from pa_agent.data.base import KlineBar
from pa_agent.data.kline_cache import KlineCacheStore, merge_bars_newest_first


def _bar(ts: float, close: float, *, seq: int = 1, closed: bool = True) -> KlineBar:
    return KlineBar(
        seq=seq,
        ts_open=ts,
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=100.0,
        amount=1000.0,
        pct_chg=None,
        closed=closed,
    )


def test_round_trip_reads_written_cache(tmp_path):
    store = KlineCacheStore(tmp_path)
    bars = [_bar(3000, 13, seq=1), _bar(2000, 12, seq=2), _bar(1000, 11, seq=3)]

    path = store.write("eastmoney", "000001", "1h", bars, max_bars=2000)
    loaded = store.read("eastmoney", "000001", "1h")

    assert path.exists()
    assert loaded is not None
    assert [b.ts_open for b in loaded.bars] == [3000, 2000, 1000]
    assert loaded.source == "eastmoney"
    assert loaded.symbol == "000001"
    assert loaded.timeframe == "1h"


def test_path_for_uses_source_directory_and_symbol_timeframe_file(tmp_path):
    store = KlineCacheStore(tmp_path)

    path = store.path_for("eastmoney", "000/001", "1h")

    assert path == tmp_path / "eastmoney" / "000_001_1h.json"


def test_merge_prefers_fetched_bar_and_sorts_newest_first():
    cached = [_bar(2000, 20), _bar(1000, 10)]
    fetched = [_bar(3000, 31), _bar(2000, 22)]

    merged = merge_bars_newest_first(cached, fetched, max_bars=10)

    assert [(b.ts_open, b.close) for b in merged] == [
        (3000, 31),
        (2000, 22),
        (1000, 10),
    ]


def test_merge_trims_to_max_bars():
    merged = merge_bars_newest_first(
        cached=[_bar(1000, 10), _bar(0, 9)],
        fetched=[_bar(3000, 13), _bar(2000, 12)],
        max_bars=3,
    )

    assert [b.ts_open for b in merged] == [3000, 2000, 1000]


def test_read_ignores_mismatched_metadata(tmp_path):
    store = KlineCacheStore(tmp_path)
    path = store.path_for("eastmoney", "000001", "1h")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "mt5",
                "symbol": "000001",
                "timeframe": "1h",
                "saved_at": "2026-06-23T00:00:00+00:00",
                "bars": [],
            }
        ),
        encoding="utf-8",
    )

    assert store.read("eastmoney", "000001", "1h") is None


def test_read_ignores_invalid_json(tmp_path):
    store = KlineCacheStore(tmp_path)
    path = store.path_for("eastmoney", "000001", "1h")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    assert store.read("eastmoney", "000001", "1h") is None


def _write_cache_payload(store: KlineCacheStore, payload: dict) -> None:
    path = store.path_for("eastmoney", "000001", "1h")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "eastmoney",
                "symbol": "000001",
                "timeframe": "1h",
                "saved_at": "2026-06-23T00:00:00+00:00",
                "bars": [payload],
            }
        ),
        encoding="utf-8",
    )


def test_read_ignores_invalid_closed_type(tmp_path):
    store = KlineCacheStore(tmp_path)
    _write_cache_payload(
        store,
        {
            "seq": 1,
            "ts_open": 1000,
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10,
            "volume": 100,
            "amount": 1000,
            "pct_chg": None,
            "closed": "definitely-not-bool",
        },
    )

    assert store.read("eastmoney", "000001", "1h") is None


def test_read_ignores_invalid_numeric_bar_fields(tmp_path):
    store = KlineCacheStore(tmp_path)
    _write_cache_payload(
        store,
        {
            "seq": 1,
            "ts_open": 1000,
            "open": 10,
            "high": "not-numeric",
            "low": 9,
            "close": 10,
            "volume": 100,
            "amount": 1000,
            "pct_chg": None,
            "closed": True,
        },
    )

    assert store.read("eastmoney", "000001", "1h") is None
