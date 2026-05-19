"""Unit tests for cost estimator and session ledger (task 6.6)."""
from __future__ import annotations

import pytest
from pa_agent.ai.deepseek_client import AIUsage
from pa_agent.ai.cost_estimator import estimate_cost, breakdown
from pa_agent.config.settings import PricingTable
from pa_agent.ai.session_ledger import SessionTokenLedger


def _pricing() -> PricingTable:
    return PricingTable(input_cache_hit=0.1, input_cache_miss=12.0, output=24.0)


def _usage(prompt: int = 1000, cached: int = 200, completion: int = 500) -> AIUsage:
    return AIUsage(
        prompt_tokens=prompt,
        cached_prompt_tokens=cached,
        completion_tokens=completion,
        total_tokens=prompt + completion,
    )


# ── estimate_cost ─────────────────────────────────────────────────────────────

def test_estimate_cost_formula():
    """estimate_cost matches the design §B.9 formula exactly."""
    p = _pricing()
    u = _usage(prompt=1000, cached=200, completion=500)
    # hit=200, miss=800, out=500
    expected = (200 * 0.1 + 800 * 12.0 + 500 * 24.0) / 1_000_000
    assert abs(estimate_cost(u, p) - expected) < 1e-12


def test_estimate_cost_all_cached():
    """When all input is cached, only cache_hit rate applies."""
    p = _pricing()
    u = AIUsage(prompt_tokens=1000, cached_prompt_tokens=1000, completion_tokens=0, total_tokens=1000)
    expected = (1000 * 0.1) / 1_000_000
    assert abs(estimate_cost(u, p) - expected) < 1e-12


def test_breakdown_keys():
    """breakdown() returns the four expected keys."""
    p = _pricing()
    u = _usage()
    bd = breakdown(u, p)
    assert set(bd.keys()) == {"cache_hit_cny", "cache_miss_cny", "output_cny", "total_cny"}
    assert abs(bd["total_cny"] - estimate_cost(u, p)) < 1e-12


# ── SessionTokenLedger ────────────────────────────────────────────────────────

def test_ledger_accumulates():
    """add() accumulates tokens and cost across multiple calls."""
    ledger = SessionTokenLedger(pricing=_pricing(), context_window=1_000_000)
    u1 = _usage(prompt=100, cached=0, completion=50)
    u2 = _usage(prompt=200, cached=50, completion=100)
    ledger.add(u1)
    ledger.add(u2)
    assert ledger.total_input == 300
    assert ledger.total_cached_input == 50
    assert ledger.total_output == 150
    assert ledger.context_used == 450
    expected_cost = estimate_cost(u1, _pricing()) + estimate_cost(u2, _pricing())
    assert abs(ledger.total_cny - expected_cost) < 1e-12


def test_ledger_yellow_threshold_fires_once():
    """Yellow threshold fires exactly once when crossing 80%."""
    events: list[str] = []
    ledger = SessionTokenLedger(pricing=_pricing(), context_window=1000, warn_pct=80.0)

    # Monkeypatch threshold_crossed signal (no Qt in tests)
    ledger._yellow_fired = False
    ledger._red_fired = False

    # Simulate crossing 80%: add 850 tokens total
    u = AIUsage(prompt_tokens=850, cached_prompt_tokens=0, completion_tokens=0, total_tokens=850)
    ledger.add(u)
    assert ledger._yellow_fired is True
    assert ledger._red_fired is False

    # Adding more should NOT re-fire yellow
    yellow_before = ledger._yellow_fired
    u2 = AIUsage(prompt_tokens=10, cached_prompt_tokens=0, completion_tokens=0, total_tokens=10)
    ledger.add(u2)
    assert ledger._yellow_fired == yellow_before  # still True, not reset


def test_ledger_red_threshold_fires_once():
    """Red threshold fires exactly once when crossing 95%."""
    ledger = SessionTokenLedger(pricing=_pricing(), context_window=1000, warn_pct=80.0)
    u = AIUsage(prompt_tokens=960, cached_prompt_tokens=0, completion_tokens=0, total_tokens=960)
    ledger.add(u)
    assert ledger._red_fired is True


def test_ledger_reset():
    """reset() clears all counters and re-arms thresholds."""
    ledger = SessionTokenLedger(pricing=_pricing(), context_window=1000, warn_pct=80.0)
    u = AIUsage(prompt_tokens=900, cached_prompt_tokens=0, completion_tokens=0, total_tokens=900)
    ledger.add(u)
    assert ledger._yellow_fired is True
    ledger.reset()
    assert ledger.total_input == 0
    assert ledger._yellow_fired is False
    assert ledger._red_fired is False
