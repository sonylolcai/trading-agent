"""Property-based tests for take_snapshot bijection invariant (task 4.8 / PR1)."""
from __future__ import annotations
import math
from hypothesis import given, assume, settings as h_settings
from hypothesis import strategies as st
from pa_agent.data.base import KlineBar
from pa_agent.data.kline_buffer import KlineBuffer
from pa_agent.data.snapshot import take_snapshot


def _make_bar(i: int, ts: float) -> KlineBar:
    return KlineBar(
        seq=i + 1, ts_open=ts,
        open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0,
        closed=True,
    )


def _fill_buffer(n_closed: int, has_forming: bool) -> KlineBuffer:
    buf = KlineBuffer(capacity=n_closed + 10)
    # Add closed bars oldest-first (append expects newest-first in the deque,
    # but we just need them in the buffer)
    for i in range(n_closed):
        buf.append(_make_bar(i, float(n_closed - i)))  # ts decreasing = newest-first
    if has_forming:
        forming = KlineBar(
            seq=1, ts_open=float(n_closed + 1),
            open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0,
            closed=False,
        )
        buf.update_forming(forming)
    return buf


@given(
    n=st.integers(min_value=2, max_value=50),
    extra=st.integers(min_value=0, max_value=20),
)
@h_settings(max_examples=200)
def test_snapshot_seq_bijection(n: int, extra: int) -> None:
    """take_snapshot returns exactly n bars with seq in {1..n}.

    **Validates: Requirements PR1.1**
    """
    buf = _fill_buffer(n_closed=n + extra, has_forming=True)
    frame = take_snapshot(buf, n, symbol="TEST", timeframe="1h")
    assert len(frame.bars) == n
    seqs = {b.seq for b in frame.bars}
    assert seqs == set(range(1, n + 1)), f"seq set mismatch: {seqs}"


@given(
    n=st.integers(min_value=2, max_value=50),
    extra=st.integers(min_value=0, max_value=20),
)
@h_settings(max_examples=200)
def test_snapshot_forming_bar_is_seq1(n: int, extra: int) -> None:
    """bars[0] has seq=1 and closed=False.

    **Validates: Requirements PR1.1**
    """
    buf = _fill_buffer(n_closed=n + extra, has_forming=True)
    frame = take_snapshot(buf, n, symbol="TEST", timeframe="1h")
    assert frame.bars[0].seq == 1
    assert frame.bars[0].closed is False


@given(
    n=st.integers(min_value=2, max_value=50),
    extra=st.integers(min_value=0, max_value=20),
)
@h_settings(max_examples=200)
def test_snapshot_ts_strictly_decreasing(n: int, extra: int) -> None:
    """bars are in strictly decreasing ts_open order (newest first).

    **Validates: Requirements PR1.1**
    """
    buf = _fill_buffer(n_closed=n + extra, has_forming=True)
    frame = take_snapshot(buf, n, symbol="TEST", timeframe="1h")
    for i in range(len(frame.bars) - 1):
        assert frame.bars[i].ts_open > frame.bars[i + 1].ts_open, (
            f"ts not strictly decreasing at index {i}: "
            f"{frame.bars[i].ts_open} <= {frame.bars[i+1].ts_open}"
        )
