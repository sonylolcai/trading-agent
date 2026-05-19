"""Unit tests for KlineBuffer (task 4.7)."""
from __future__ import annotations
import pytest
from pa_agent.data.base import KlineBar
from pa_agent.data.kline_buffer import KlineBuffer


def _bar(seq: int, ts: float, closed: bool = True) -> KlineBar:
    return KlineBar(seq=seq, ts_open=ts, open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0, closed=closed)


def test_capacity_trim():
    """Buffer trims oldest bars beyond capacity."""
    buf = KlineBuffer(capacity=3)
    for i in range(5):
        buf.append(_bar(i + 1, float(i)))
    assert buf.size <= 4  # 3 closed + possibly 1 forming


def test_update_forming_does_not_affect_closed():
    """update_forming only changes the forming slot, not closed bars."""
    buf = KlineBuffer(capacity=10)
    buf.append(_bar(1, 1.0))
    buf.append(_bar(2, 2.0))
    forming = _bar(3, 3.0, closed=False)
    buf.update_forming(forming)
    view = buf.snapshot_view()
    assert view[0].ts_open == 3.0
    assert view[0].closed is False
    # Closed bars are untouched
    closed_ts = [b.ts_open for b in view[1:]]
    assert 1.0 in closed_ts
    assert 2.0 in closed_ts


def test_last_n_no_duplicate_ts_on_forming_flip():
    """last_n_including_forming returns no duplicate ts_open when forming flips."""
    buf = KlineBuffer(capacity=10)
    # Simulate: forming bar at ts=3, then it closes and a new forming appears
    buf.update_forming(_bar(1, 3.0, closed=False))
    buf.append(_bar(1, 3.0, closed=True))   # same ts — bar just closed
    buf.update_forming(_bar(2, 4.0, closed=False))  # new forming bar
    bars = buf.last_n_including_forming(5)
    ts_list = [b.ts_open for b in bars]
    assert len(ts_list) == len(set(ts_list)), "duplicate ts_open found"


def test_clear_resets_buffer():
    """clear() removes all bars."""
    buf = KlineBuffer(capacity=10)
    buf.append(_bar(1, 1.0))
    buf.update_forming(_bar(2, 2.0, closed=False))
    buf.clear()
    assert buf.size == 0
    assert buf.last_n_including_forming(5) == []


def test_last_n_returns_at_most_n():
    """last_n_including_forming returns at most n bars."""
    buf = KlineBuffer(capacity=20)
    for i in range(10):
        buf.append(_bar(i + 1, float(i)))
    buf.update_forming(_bar(11, 10.0, closed=False))
    result = buf.last_n_including_forming(5)
    assert len(result) == 5
