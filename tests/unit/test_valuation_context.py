"""Tests for deterministic, non-binding A-share valuation context."""
from __future__ import annotations

from pa_agent.valuation.context import build_valuation_context


def test_non_stock_symbol_is_not_applicable() -> None:
    context = build_valuation_context("BTC-USDT", now_ms=123)

    assert context.available is False
    assert context.source == "none"
    assert context.data_quality == "not_applicable"
    assert context.to_payload()["risk_flags"] == []


def test_complete_snapshot_is_deterministic_and_non_binding() -> None:
    context = build_valuation_context(
        "SZ000001",
        now_ms=123,
        fetcher=lambda _symbol: {
            "pe_dynamic": 12,
            "pb": 1.1,
            "roe": 16,
            "debt_to_asset": 35,
            "net_profit_yoy": 24,
        },
    )

    assert context.available is True
    assert context.symbol == "000001"
    assert context.data_quality == "complete"
    assert (context.valuation_level, context.quality_level, context.growth_level) == (
        "cheap",
        "strong",
        "strong",
    )
    assert context.valuation_score == 85
    assert context.quality_score == 85
    assert "不能单独否决或建立交易" in context.to_prompt_block()


def test_partial_and_risky_snapshot_exposes_flags_without_failing() -> None:
    context = build_valuation_context(
        "600000",
        now_ms=123,
        fetcher=lambda _symbol: {
            "pe_dynamic": 90,
            "pb": 7,
            "roe": 3,
            "debt_to_asset": 82,
            "net_profit_yoy": -5,
        },
    )

    assert context.available is True
    assert context.valuation_level == "expensive"
    assert context.quality_level == "weak"
    assert context.growth_level == "weak"
    assert set(context.risk_flags) == {
        "动态 PE 较高",
        "PB 较高",
        "ROE 偏低",
        "资产负债率偏高",
        "净利润同比为负",
    }


def test_provider_failure_falls_back_without_analysis_failure() -> None:
    def failing_fetcher(_symbol: str) -> dict[str, object]:
        raise RuntimeError("provider unavailable")

    context = build_valuation_context("000001", fetcher=failing_fetcher, now_ms=123)

    assert context.available is False
    assert context.data_quality == "unavailable"
    assert "回退为价格行为分析" in context.note


def test_loss_making_company_is_never_cheap() -> None:
    context = build_valuation_context(
        "600999",
        now_ms=123,
        fetcher=lambda _symbol: {
            "pe_dynamic": -12.5,
            "pb": 0.8,
            "roe": -5,
            "debt_to_asset": 78,
            "net_profit_yoy": -30,
        },
    )

    assert context.available is True
    assert context.valuation_level == "expensive"
    assert "盈利为负或动态 PE 不适用" in context.risk_flags
