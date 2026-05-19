"""Property-based tests for ExceptionCounter monotonicity (task 9.3 / PR4).

**Validates: Requirements PR4**

Properties tested:
- After failure (ValidationError) events, consecutive_count is monotonically
  non-decreasing.
- RoundTripSuccess immediately resets consecutive_count to zero.
- UserCancel and NetworkError do not change consecutive_count.
- save → reconstruct ExceptionCounter → load results in fully equal state.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from hypothesis import HealthCheck, given, settings as h_settings
from hypothesis import strategies as st

from pa_agent.orchestrator.exception_counter import ExceptionCounter


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_validation_error() -> Any:
    """Return a minimal mock ValidationError compatible with ExceptionCounter."""
    err = MagicMock()
    err.category = "b"
    err.raw_text = "test raw text"
    err.parse_position = None
    err.missing_fields = ["cycle_position"]
    err.invalid_fields = []
    err.allowed_values = {}
    return err


def _make_counter(state_file: Path) -> ExceptionCounter:
    """Create a fresh ExceptionCounter backed by *state_file*."""
    return ExceptionCounter(state_path=state_file, event_bus=None)


def _apply_events(counter: ExceptionCounter, events: list[str]) -> list[int]:
    """Apply a sequence of events to *counter* and return count snapshots.

    Returns a list of consecutive_count values *after* each event.
    """
    snapshots: list[int] = []
    err = _make_validation_error()
    for event in events:
        if event == "validation_error":
            counter.on_validation_error("stage1", err)
        elif event == "round_trip_success":
            counter.on_round_trip_success()
        elif event == "user_cancel":
            counter.on_user_cancel("test_reason")
        elif event == "network_error":
            counter.on_network_error(Exception("network timeout"))
        snapshots.append(counter.consecutive_count)
    return snapshots


# ── Property 1: validation_error events are monotonically non-decreasing ──────

@given(
    st.lists(
        st.sampled_from(["validation_error", "round_trip_success", "user_cancel", "network_error"]),
        min_size=1,
        max_size=30,
    )
)
@h_settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_failure_events_monotone_non_decreasing(events: list[str]) -> None:
    """After each validation_error, consecutive_count must be >= the previous count.

    **Validates: Requirements PR4.1(i)**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "exception_state.json"
        counter = _make_counter(state_file)
        counter.load()

        err = _make_validation_error()
        for event in events:
            before = counter.consecutive_count
            if event == "validation_error":
                counter.on_validation_error("stage1", err)
                # After a validation error, count must be strictly greater than before
                assert counter.consecutive_count > before, (
                    f"Expected count to increase after validation_error, "
                    f"was {before}, now {counter.consecutive_count}"
                )
            elif event == "round_trip_success":
                counter.on_round_trip_success()
            elif event == "user_cancel":
                counter.on_user_cancel("reason")
            elif event == "network_error":
                counter.on_network_error(Exception("err"))


# ── Property 2: RoundTripSuccess immediately resets count to zero ─────────────

@given(
    st.integers(min_value=1, max_value=20),
    st.lists(
        st.sampled_from(["user_cancel", "network_error"]),
        max_size=5,
    ),
)
@h_settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_round_trip_success_resets_to_zero(
    n_failures: int, trailing_events: list[str]
) -> None:
    """RoundTripSuccess must immediately set consecutive_count to 0.

    **Validates: Requirements PR4.1(ii)**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "exception_state.json"
        counter = _make_counter(state_file)
        counter.load()

        err = _make_validation_error()
        # Build up a streak of n_failures
        for _ in range(n_failures):
            counter.on_validation_error("stage1", err)

        assert counter.consecutive_count == n_failures

        # A round-trip success must reset to zero immediately
        counter.on_round_trip_success()
        assert counter.consecutive_count == 0, (
            f"Expected consecutive_count == 0 after RoundTripSuccess, "
            f"got {counter.consecutive_count}"
        )

        # Any trailing non-failure events must not change the zero
        for event in trailing_events:
            if event == "user_cancel":
                counter.on_user_cancel("reason")
            elif event == "network_error":
                counter.on_network_error(Exception("err"))
            assert counter.consecutive_count == 0, (
                f"consecutive_count changed from 0 after {event}: "
                f"got {counter.consecutive_count}"
            )


# ── Property 3: UserCancel and NetworkError do not change count ───────────────

@given(
    st.integers(min_value=0, max_value=15),
    st.lists(
        st.sampled_from(["user_cancel", "network_error"]),
        min_size=1,
        max_size=20,
    ),
)
@h_settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_user_cancel_and_network_error_do_not_change_count(
    initial_failures: int, neutral_events: list[str]
) -> None:
    """UserCancel and NetworkError must not change consecutive_count.

    **Validates: Requirements PR4.1 (R8.8, R8.9)**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "exception_state.json"
        counter = _make_counter(state_file)
        counter.load()

        err = _make_validation_error()
        # Establish an initial count
        for _ in range(initial_failures):
            counter.on_validation_error("stage1", err)

        expected_count = counter.consecutive_count

        # Apply neutral events — count must remain unchanged
        for event in neutral_events:
            if event == "user_cancel":
                counter.on_user_cancel("switched_symbol")
            elif event == "network_error":
                counter.on_network_error(Exception("timeout"))

            assert counter.consecutive_count == expected_count, (
                f"consecutive_count changed after {event}: "
                f"expected {expected_count}, got {counter.consecutive_count}"
            )


# ── Property 4: save → reconstruct → load yields fully equal state ────────────

@given(
    st.lists(
        st.sampled_from(["validation_error", "round_trip_success", "user_cancel", "network_error"]),
        min_size=0,
        max_size=25,
    )
)
@h_settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_save_reconstruct_load_equal_state(events: list[str]) -> None:
    """save → reconstruct ExceptionCounter → load results in fully equal state.

    **Validates: Requirements PR4.1(iii)**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "exception_state.json"

        # Build up state via events
        counter1 = ExceptionCounter(state_path=state_file, event_bus=None)
        counter1.load()
        _apply_events(counter1, events)

        # Explicitly save (on_* methods already call save, but be explicit)
        counter1.save()

        # Reconstruct a fresh counter from the same file
        counter2 = ExceptionCounter(state_path=state_file, event_bus=None)
        counter2.load()

        # All observable state fields must be equal
        assert counter2.consecutive_count == counter1.consecutive_count, (
            f"consecutive_count mismatch after reload: "
            f"expected {counter1.consecutive_count}, got {counter2.consecutive_count}"
        )
        assert counter2.last_error_category == counter1.last_error_category, (
            f"last_error_category mismatch: "
            f"expected {counter1.last_error_category!r}, got {counter2.last_error_category!r}"
        )
        assert counter2.last_error_at_ms == counter1.last_error_at_ms, (
            f"last_error_at_ms mismatch: "
            f"expected {counter1.last_error_at_ms}, got {counter2.last_error_at_ms}"
        )
        # History must also be equal (same entries, same order)
        assert counter2._state.history == counter1._state.history, (
            f"history mismatch after reload: "
            f"expected {len(counter1._state.history)} entries, "
            f"got {len(counter2._state.history)} entries"
        )


# ── Property 5: history never exceeds 50 entries ─────────────────────────────

@given(
    st.integers(min_value=51, max_value=120),
)
@h_settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_history_capped_at_50(n_events: int) -> None:
    """History list must never exceed 50 entries regardless of event count.

    **Validates: Requirements PR4 (design §B.8 _MAX_HISTORY)**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "exception_state.json"
        counter = _make_counter(state_file)
        counter.load()

        err = _make_validation_error()
        # Mix of all event types to stress the history cap
        for i in range(n_events):
            event_type = i % 4
            if event_type == 0:
                counter.on_validation_error("stage1", err)
            elif event_type == 1:
                counter.on_round_trip_success()
            elif event_type == 2:
                counter.on_user_cancel("reason")
            else:
                counter.on_network_error(Exception("err"))

        assert len(counter._state.history) <= 50, (
            f"History exceeded 50 entries: got {len(counter._state.history)}"
        )
