"""Tests for the full PA workflow replay harness.

The fakes deliberately return different decisions for the two experiment arms;
the assertions verify that their *input funnel* is still identical and that
volume is only supplied to the experimental arm.
"""
from __future__ import annotations

from dataclasses import dataclass

from pa_agent.ai.volume_context import VolumePriceContext, build_volume_price_context
from pa_agent.backtest.full_flow import (
    FastScreenResult,
    FullFlowABBacktester,
    FullFlowConfig,
    FullFlowSummary,
    JsonReplayCache,
    PipelineResult,
    PrefilterResult,
    _parse_fast_screen_reply,
    build_fast_screen_messages,
)
from pa_agent.backtest.metrics import calculate_metrics
from pa_agent.backtest.simulator import TradeSimulation
from pa_agent.data.base import IndicatorBundle, KlineBar, KlineFrame


def _frame_with_volume_context() -> KlineFrame:
    bars = tuple(
        KlineBar(
            seq=index + 1,
            ts_open=10_000 - index,
            open=100.0,
            high=110.0,
            low=100.0,
            close=109.0,
            volume=200.0 if index == 0 else 100.0,
            closed=True,
        )
        for index in range(21)
    )
    return KlineFrame(
        symbol="TEST",
        timeframe="1d",
        bars=bars,
        indicators=IndicatorBundle(ema20=(100.0,) * 21, atr14=(2.0,) * 21),
        snapshot_ts_local_ms=10_000,
    )


def test_volume_context_is_as_of_and_only_present_in_experimental_screen_prompt() -> None:
    frame = _frame_with_volume_context()
    context = build_volume_price_context(frame)

    assert context.available is True
    assert context.relative_volume == 2.0
    assert context.reference_bar_count == 20
    assert context.condition == "expanded_volume_strong_close"

    prefilter = PrefilterResult(True, "bullish", "K1 closes above the prior range")
    baseline = build_fast_screen_messages(
        frame=frame,
        prefilter=prefilter,
        volume_context=None,
    )[1]["content"]
    assisted = build_fast_screen_messages(
        frame=frame,
        prefilter=prefilter,
        volume_context=context,
    )[1]["content"]
    assert "量价辅助上下文" not in baseline
    assert "量价辅助上下文" in assisted
    assert "K2-K21" in assisted


def test_fast_screen_string_false_fails_closed() -> None:
    """Provider enum slips must not accidentally spend a full Stage 1/2 call."""

    class Reply:
        content = '{"candidate":"false","confidence":"90","reason":"no setup"}'
        latency_ms = 1.0
        usage = None

    result = _parse_fast_screen_reply(Reply())

    assert result.proceed is False
    assert result.confidence == 90


def test_full_flow_payload_distinguishes_no_order_from_invalid_prices() -> None:
    """A deliberate Stage-2 wait must not be labelled as invalid geometry."""

    simulations = (
        TradeSimulation("skipped", 0.0, False, None, 0, "no trade order"),
        TradeSimulation("invalid", 0.0, False, None, 0, "invalid price geometry"),
    )
    summary = FullFlowSummary(
        variant="price_only",
        logic_candidates=2,
        screened_out=0,
        full_pipeline_runs=2,
        pipeline_failures=0,
        skipped_active_position=0,
        simulations=simulations,
        metrics=calculate_metrics(simulations),
        total_r=0.0,
        usage_total={},
        latency_ms=0.0,
        trades=(),
    )

    payload = summary.to_payload()

    assert payload["no_order_decisions"] == 1
    assert payload["invalid_price_geometry"] == 1
    assert "invalid_decisions" not in payload


def _historical_bars() -> list[KlineBar]:
    """Chronological bars whose K1 repeatedly passes the price-only prefilter."""
    bars: list[KlineBar] = []
    for index in range(28):
        base = 100.0 + index
        bars.append(
            KlineBar(
                seq=1,
                ts_open=float(index),
                open=base,
                high=base + 1.0,
                low=base - 1.0,
                close=base + 0.9,
                volume=200.0 if index % 3 == 0 else 100.0,
                closed=True,
            )
        )
    return bars


@dataclass
class _FakeScreener:
    calls: list[VolumePriceContext | None]

    def screen(
        self,
        *,
        frame: KlineFrame,
        prefilter: PrefilterResult,
        volume_context: VolumePriceContext | None,
    ) -> FastScreenResult:
        assert prefilter.is_candidate is True
        self.calls.append(volume_context)
        return FastScreenResult(
            proceed=True,
            confidence=80,
            reason="price candidate accepted",
            usage_total={"total_tokens": 7},
            latency_ms=2.0,
        )


@dataclass
class _FakePipeline:
    calls: list[tuple[str, VolumePriceContext | None]]

    def run(
        self,
        *,
        frame: KlineFrame,
        variant: str,
        volume_context: VolumePriceContext | None,
    ) -> PipelineResult:
        self.calls.append((variant, volume_context))
        close = float(frame.bars[0].close)
        return PipelineResult(
            stage2_decision={
                "decision": {
                    "order_direction": "做多",
                    "order_type": "市价单",
                    "entry_price": close,
                    "take_profit_price": close + 0.5,
                    "stop_loss_price": close - 1.0,
                }
            },
            usage_total={"total_tokens": 11},
            latency_ms=3.0,
            exception=None,
        )


def test_full_flow_runs_same_price_candidates_then_passes_volume_only_to_b_arm(tmp_path) -> None:
    screener = _FakeScreener(calls=[])
    pipeline = _FakePipeline(calls=[])
    runner = FullFlowABBacktester(
        fast_screener=screener,
        pipeline=pipeline,
        config=FullFlowConfig(window_bars=20, max_holding_bars=5, model_revision="fake-v1"),
        cache=JsonReplayCache(tmp_path / "replay-cache"),
    )

    comparison = runner.run(symbol="TEST", timeframe="1d", bars=_historical_bars())

    assert comparison.candidate_timestamps
    assert comparison.price_only.logic_candidates == comparison.volume_assisted.logic_candidates
    assert comparison.price_only.full_pipeline_runs > 0
    assert comparison.volume_assisted.full_pipeline_runs > 0
    assert any(context is None for context in screener.calls)
    assert any(context is not None for context in screener.calls)
    assert all(context is None for variant, context in pipeline.calls if variant == "price_only")
    assert all(context is not None for variant, context in pipeline.calls if variant == "volume_assisted")
    assert comparison.price_only.usage_total["total_tokens"] > 0
    assert comparison.volume_assisted.usage_total["total_tokens"] > 0

    # A second replay with identical data reads both model stages from cache.
    cached_screener = _FakeScreener(calls=[])
    cached_pipeline = _FakePipeline(calls=[])
    cached = FullFlowABBacktester(
        fast_screener=cached_screener,
        pipeline=cached_pipeline,
        config=FullFlowConfig(window_bars=20, max_holding_bars=5, model_revision="fake-v1"),
        cache=JsonReplayCache(tmp_path / "replay-cache"),
    ).run(symbol="TEST", timeframe="1d", bars=_historical_bars())

    assert cached.to_payload() == comparison.to_payload()
    assert cached_screener.calls == []
    assert cached_pipeline.calls == []
