"""Bar-by-bar replay of the complete PA workflow for controlled A/B research.

This module intentionally sits beside, rather than inside, the lightweight
``rolling`` dashboard proxy.  It replays each historical timestamp as a fresh
as-of snapshot, applies one shared deterministic price-action filter, calls a
compact LLM screen, then invokes the normal Stage 1 -> routing -> Stage 2 ->
validation path through an adapter.  The volume group differs only by the
additional immutable ``VolumePriceContext`` supplied to its two LLM prompts.

The runner does not enable volume in live trading.  It is an auditable research
harness and requires an explicitly supplied workflow and fast-screen client.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Literal, Protocol

from pa_agent.ai.volume_context import VolumePriceContext, build_volume_price_context
from pa_agent.backtest.metrics import BacktestMetrics, calculate_metrics
from pa_agent.backtest.simulator import TradeSimulation, simulate_decision
from pa_agent.data.base import KlineBar, KlineFrame
from pa_agent.data.snapshot import build_analysis_frame


ExperimentVariant = Literal["price_only", "volume_assisted"]
EXPERIMENT_VARIANTS: tuple[ExperimentVariant, ...] = ("price_only", "volume_assisted")
FULL_FLOW_PROMPT_REVISION = "full-flow-volume-ab-v2"


@dataclass(frozen=True)
class PrefilterResult:
    """Label-free deterministic screening result shared by both experiment arms."""

    is_candidate: bool
    direction: Literal["bullish", "bearish"] | None
    reason: str


@dataclass(frozen=True)
class FastScreenResult:
    """Normalized output of the short, inexpensive LLM screening prompt."""

    proceed: bool
    confidence: int
    reason: str
    usage_total: dict[str, int]
    latency_ms: float

    def to_payload(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FastScreenResult":
        return cls(
            proceed=bool(payload.get("proceed", False)),
            confidence=int(payload.get("confidence", 0) or 0),
            reason=str(payload.get("reason", "")),
            usage_total=_normalize_usage(payload.get("usage_total")),
            latency_ms=float(payload.get("latency_ms", 0.0) or 0.0),
        )


@dataclass(frozen=True)
class PipelineResult:
    """Minimal serializable outcome needed after the normal Stage 1/2 workflow."""

    stage2_decision: dict[str, Any] | None
    usage_total: dict[str, int]
    latency_ms: float
    exception: dict[str, Any] | None

    def to_payload(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PipelineResult":
        decision = payload.get("stage2_decision")
        exception = payload.get("exception")
        return cls(
            stage2_decision=decision if isinstance(decision, dict) else None,
            usage_total=_normalize_usage(payload.get("usage_total")),
            latency_ms=float(payload.get("latency_ms", 0.0) or 0.0),
            exception=exception if isinstance(exception, dict) else None,
        )


@dataclass(frozen=True)
class FullFlowTrade:
    """One persisted replay attempt, including skips for an auditable funnel."""

    variant: ExperimentVariant
    signal_ts_open: float
    prefilter: PrefilterResult
    fast_screen: FastScreenResult | None
    pipeline: PipelineResult | None
    simulation: TradeSimulation | None
    skipped_reason: str | None = None


@dataclass(frozen=True)
class FullFlowSummary:
    """Metrics and cost/coverage observability for one A/B arm."""

    variant: ExperimentVariant
    logic_candidates: int
    screened_out: int
    full_pipeline_runs: int
    pipeline_failures: int
    skipped_active_position: int
    simulations: tuple[TradeSimulation, ...]
    metrics: BacktestMetrics
    total_r: float
    usage_total: dict[str, int]
    latency_ms: float
    trades: tuple[FullFlowTrade, ...]

    def to_payload(self) -> dict[str, object]:
        completed = self.metrics.wins + self.metrics.losses
        no_order_decisions = sum(
            simulation.status == "skipped" for simulation in self.simulations
        )
        invalid_price_geometry = sum(
            simulation.status == "invalid" for simulation in self.simulations
        )
        return {
            "variant": self.variant,
            "logic_candidates": self.logic_candidates,
            "screened_out": self.screened_out,
            "full_pipeline_runs": self.full_pipeline_runs,
            "pipeline_failures": self.pipeline_failures,
            "skipped_active_position": self.skipped_active_position,
            "trade_signals": self.metrics.total_signals,
            "triggered_trades": self.metrics.triggered_trades,
            "completed_trades": completed,
            "open_trades": self.metrics.open_trades,
            "not_triggered": self.metrics.not_triggered,
            # ``BacktestMetrics.invalid`` intentionally aggregates both statuses
            # for generic reporting.  The full-flow A/B report must distinguish
            # an intentional Stage-2 "no order" decision from malformed prices.
            "no_order_decisions": no_order_decisions,
            "invalid_price_geometry": invalid_price_geometry,
            "win_rate_pct": self.metrics.win_rate_pct,
            "expectancy_r": self.metrics.expectancy_r,
            "total_r": self.total_r,
            "max_drawdown_r": self.metrics.max_drawdown_r,
            "usage_total": dict(self.usage_total),
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True)
class FullFlowComparison:
    """The complete A/B result; both arms begin from the same price candidates."""

    symbol: str
    timeframe: str
    window_bars: int
    candidate_timestamps: tuple[float, ...]
    price_only: FullFlowSummary
    volume_assisted: FullFlowSummary

    def to_payload(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "window_bars": self.window_bars,
            "candidate_count": len(self.candidate_timestamps),
            "price_only": self.price_only.to_payload(),
            "volume_assisted": self.volume_assisted.to_payload(),
        }


@dataclass(frozen=True)
class FullFlowConfig:
    """Fixed replay controls; change them only as a new recorded experiment."""

    window_bars: int = 100
    max_logic_candidates: int = 40
    max_holding_bars: int | None = 30
    single_active_position: bool = True
    transaction_cost_r: float = 0.0
    prompt_revision: str = FULL_FLOW_PROMPT_REVISION
    model_revision: str = "unspecified-model"


class FastScreener(Protocol):
    """Small-model screening boundary used by the historical runner."""

    def screen(
        self,
        *,
        frame: KlineFrame,
        prefilter: PrefilterResult,
        volume_context: VolumePriceContext | None,
    ) -> FastScreenResult: ...


class FullPipeline(Protocol):
    """Adapter boundary that must execute the real Stage 1/Stage 2 workflow."""

    def run(
        self,
        *,
        frame: KlineFrame,
        variant: ExperimentVariant,
        volume_context: VolumePriceContext | None,
    ) -> PipelineResult: ...


class JsonReplayCache:
    """Small file cache keyed by full as-of input, variant, model and prompt revision.

    Cache entries contain model outputs and token counts but never provider
    credentials.  Corrupt or incompatible entries are treated as cache misses.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def get(self, stage: str, key: str) -> dict[str, Any] | None:
        path = self._root / stage / f"{key}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def put(self, stage: str, key: str, payload: dict[str, object]) -> None:
        path = self._root / stage / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)


class PriceActionCandidateFilter:
    """Cheap, deterministic breakout filter used before any LLM request.

    It is intentionally broad and only observes K1 plus K2-K6.  It does not
    read volume, outcomes, or future bars, so A and B always receive the same
    set of initial timestamps.
    """

    def __init__(self, *, lookback_bars: int = 5, min_close_position: float = 0.6) -> None:
        self._lookback_bars = max(2, int(lookback_bars))
        self._min_close_position = min(1.0, max(0.5, float(min_close_position)))

    def evaluate(self, frame: KlineFrame) -> PrefilterResult:
        closed = [bar for bar in frame.bars if bool(getattr(bar, "closed", True))]
        if len(closed) <= self._lookback_bars:
            return PrefilterResult(False, None, "insufficient closed bars for price filter")

        latest = closed[0]
        prior = closed[1 : self._lookback_bars + 1]
        price_range = float(latest.high) - float(latest.low)
        if price_range <= 0:
            return PrefilterResult(False, None, "latest bar has no usable range")

        close_position = (float(latest.close) - float(latest.low)) / price_range
        prior_high = max(float(bar.high) for bar in prior)
        prior_low = min(float(bar.low) for bar in prior)
        if (
            float(latest.close) > float(latest.open)
            and float(latest.close) >= prior_high
            and close_position >= self._min_close_position
        ):
            return PrefilterResult(True, "bullish", "K1 bullish close breaks the prior price range")
        if (
            float(latest.close) < float(latest.open)
            and float(latest.close) <= prior_low
            and close_position <= 1.0 - self._min_close_position
        ):
            return PrefilterResult(True, "bearish", "K1 bearish close breaks the prior price range")
        return PrefilterResult(False, None, "no closed price breakout candidate")


def _compact_bars(frame: KlineFrame, *, count: int = 6) -> str:
    """Render only the newest small window for the inexpensive LLM screen."""
    rows = ["bar | open | high | low | close"]
    for bar in frame.bars[: max(1, int(count))]:
        rows.append(
            f"K{bar.seq} | {bar.open:.4f} | {bar.high:.4f} | {bar.low:.4f} | {bar.close:.4f}"
        )
    return "\n".join(rows)


def build_fast_screen_messages(
    *,
    frame: KlineFrame,
    prefilter: PrefilterResult,
    volume_context: VolumePriceContext | None,
) -> list[dict[str, str]]:
    """Build a bounded JSON-only prompt for the low-cost screening call."""
    volume_block = volume_context.to_prompt_block() if volume_context is not None else ""
    return [
        {
            "role": "system",
            "content": (
                "你是价格行为交易研究的快速筛选器。只判断是否值得调用完整阶段一和阶段二；"
                "不制定订单，不预测收益。必须只输出 JSON。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"品种={frame.symbol}，周期={frame.timeframe}。以下是最近 K 线：\n{_compact_bars(frame)}\n\n"
                f"程序已用纯价格规则确认候选：方向={prefilter.direction}；依据={prefilter.reason}。\n"
                "不要重复否定该突破是否存在；你的任务仅检查最新 K 线是否有明显反向失效、"
                "极端混乱或数据矛盾。若没有明确反证，candidate=true 并交给完整 Stage 1/2；"
                "只有存在具体反证时才 candidate=false。\n"
                "返回严格 JSON：{\"candidate\":true|false,\"confidence\":0-100,\"reason\":\"简短中文理由\"}。\n\n"
                f"{volume_block}"
            ),
        },
    ]


def _normalize_usage(value: object) -> dict[str, int]:
    """Keep only numeric, additive provider usage fields."""
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, raw in value.items():
        try:
            result[str(key)] = int(raw)
        except (TypeError, ValueError):
            continue
    return result


def _reply_usage(reply: Any) -> dict[str, int]:
    usage = getattr(reply, "usage", None)
    if usage is None:
        return {}
    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "cached_prompt_tokens": int(getattr(usage, "cached_prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def _parse_fast_screen_reply(reply: Any) -> FastScreenResult:
    """Parse a tolerant provider reply while retaining a safe fail-closed default."""
    content = str(getattr(reply, "content", reply) or "").strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else ""
        content = content.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = {}
    candidate = parsed.get("candidate") if isinstance(parsed, dict) else False
    confidence = parsed.get("confidence", 0) if isinstance(parsed, dict) else 0
    reason = parsed.get("reason", "invalid fast-screen JSON") if isinstance(parsed, dict) else "invalid fast-screen JSON"
    try:
        confidence_i = max(0, min(100, int(confidence)))
    except (TypeError, ValueError):
        confidence_i = 0
    if isinstance(candidate, str):
        proceed = candidate.strip().lower() in {"true", "1", "yes", "proceed"}
    else:
        proceed = candidate is True or candidate == 1
    return FastScreenResult(
        proceed=proceed,
        confidence=confidence_i,
        reason=str(reason),
        usage_total=_reply_usage(reply),
        latency_ms=float(getattr(reply, "latency_ms", 0.0) or 0.0),
    )


class CompactLLMScreener:
    """Use an OpenAI-compatible client for the short screening stage only."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def screen(
        self,
        *,
        frame: KlineFrame,
        prefilter: PrefilterResult,
        volume_context: VolumePriceContext | None,
    ) -> FastScreenResult:
        reply = self._client.chat(
            build_fast_screen_messages(
                frame=frame,
                prefilter=prefilter,
                volume_context=volume_context,
            ),
            thinking=False,
            reasoning_effort="low",
        )
        return _parse_fast_screen_reply(reply)


class OrchestratorPipelineAdapter:
    """Invoke the existing production two-stage orchestrator without bypassing it."""

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def run(
        self,
        *,
        frame: KlineFrame,
        variant: ExperimentVariant,
        volume_context: VolumePriceContext | None,
    ) -> PipelineResult:
        from pa_agent.util.threading import CancelToken

        record = self._orchestrator.submit(
            frame=frame,
            cancel_token=CancelToken(),
            on_event=lambda _event: None,
            volume_context=volume_context,
            analysis_variant=variant,
        )
        stage_latencies = (
            (record.stage1_response or {}).get("latency_ms", 0.0),
            (record.stage2_response or {}).get("latency_ms", 0.0),
        )
        return PipelineResult(
            stage2_decision=record.stage2_decision,
            usage_total=_normalize_usage(record.usage_total),
            latency_ms=sum(float(value or 0.0) for value in stage_latencies),
            exception=record.exception,
        )


def _accumulate_usage(total: dict[str, int], delta: dict[str, int]) -> None:
    for key, value in delta.items():
        total[key] = total.get(key, 0) + int(value)


def _cache_key(
    *,
    stage: str,
    frame: KlineFrame,
    variant: ExperimentVariant,
    volume_context: VolumePriceContext | None,
    prefilter: PrefilterResult,
    config: FullFlowConfig,
) -> str:
    """Hash all model-relevant as-of inputs, not a future outcome or order result."""
    payload = {
        "stage": stage,
        "symbol": frame.symbol,
        "timeframe": frame.timeframe,
        "variant": variant,
        "model_revision": config.model_revision,
        "prompt_revision": config.prompt_revision,
        "bars": [
            {
                "ts_open": bar.ts_open,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in frame.bars
        ],
        "volume_context": volume_context.to_payload() if volume_context is not None else None,
        "prefilter": asdict(prefilter),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _apply_transaction_cost(result: TradeSimulation, cost_r: float) -> TradeSimulation:
    """Apply explicit fixed friction after a terminal trade without hiding it in prices."""
    if not result.entry_triggered or result.status not in {"win", "loss"} or cost_r <= 0:
        return result
    adjusted_r = float(result.r_multiple) - cost_r
    return replace(
        result,
        r_multiple=adjusted_r,
        status="win" if adjusted_r > 0 else "loss",
        reason=f"{result.reason}; transaction_cost_r={cost_r:.4f}",
    )


class FullFlowABBacktester:
    """Run a frozen two-arm experiment across all historical as-of snapshots."""

    def __init__(
        self,
        *,
        fast_screener: FastScreener,
        pipeline: FullPipeline,
        config: FullFlowConfig = FullFlowConfig(),
        candidate_filter: PriceActionCandidateFilter | None = None,
        cache: JsonReplayCache | None = None,
    ) -> None:
        self._fast_screener = fast_screener
        self._pipeline = pipeline
        self._config = config
        self._candidate_filter = candidate_filter or PriceActionCandidateFilter()
        self._cache = cache

    def run(
        self,
        *,
        symbol: str,
        timeframe: str,
        bars: Iterable[KlineBar],
    ) -> FullFlowComparison:
        """Replay historical bars chronologically, with no future data in each frame."""
        window = max(20, int(self._config.window_bars))
        chronological = sorted(
            (bar for bar in bars if bool(getattr(bar, "closed", True))),
            key=lambda bar: float(bar.ts_open),
        )
        ledgers = {variant: _VariantLedger(variant) for variant in EXPERIMENT_VARIANTS}
        candidate_timestamps: list[float] = []
        next_eligible_index = {variant: 0 for variant in EXPERIMENT_VARIANTS}

        for as_of_index in range(window - 1, len(chronological)):
            # The frame is built from only the history available on this date.
            history_newest_first = list(reversed(chronological[: as_of_index + 1]))
            frame = build_analysis_frame(history_newest_first, window, symbol, timeframe)
            if frame is None:
                continue
            prefilter = self._candidate_filter.evaluate(frame)
            if not prefilter.is_candidate:
                continue

            # A full two-stage call is intentionally expensive.  Stop only on
            # the common, label-free prefilter so neither experiment arm gets
            # preferential coverage or a different historical date range.
            if len(candidate_timestamps) >= max(1, int(self._config.max_logic_candidates)):
                break

            candidate_timestamps.append(float(frame.bars[0].ts_open))
            computed_volume_context = build_volume_price_context(frame)
            future_bars = chronological[as_of_index + 1 :]

            for variant in EXPERIMENT_VARIANTS:
                ledger = ledgers[variant]
                volume_context = computed_volume_context if variant == "volume_assisted" else None
                ledger.logic_candidates += 1
                if self._config.single_active_position and as_of_index < next_eligible_index[variant]:
                    ledger.skipped_active_position += 1
                    ledger.trades.append(
                        FullFlowTrade(
                            variant=variant,
                            signal_ts_open=float(frame.bars[0].ts_open),
                            prefilter=prefilter,
                            fast_screen=None,
                            pipeline=None,
                            simulation=None,
                            skipped_reason="single active position is still open",
                        )
                    )
                    continue

                fast_screen = self._screen(frame, prefilter, variant, volume_context)
                _accumulate_usage(ledger.usage_total, fast_screen.usage_total)
                ledger.latency_ms += fast_screen.latency_ms
                if not fast_screen.proceed:
                    ledger.screened_out += 1
                    ledger.trades.append(
                        FullFlowTrade(
                            variant=variant,
                            signal_ts_open=float(frame.bars[0].ts_open),
                            prefilter=prefilter,
                            fast_screen=fast_screen,
                            pipeline=None,
                            simulation=None,
                            skipped_reason="fast screen declined full pipeline",
                        )
                    )
                    continue

                pipeline = self._run_pipeline(frame, prefilter, variant, volume_context)
                ledger.full_pipeline_runs += 1
                _accumulate_usage(ledger.usage_total, pipeline.usage_total)
                ledger.latency_ms += pipeline.latency_ms
                if pipeline.exception is not None:
                    ledger.pipeline_failures += 1

                simulation = _apply_transaction_cost(
                    simulate_decision(
                        pipeline.stage2_decision or {},
                        future_bars,
                        max_holding_bars=self._config.max_holding_bars,
                    ),
                    self._config.transaction_cost_r,
                )
                ledger.simulations.append(simulation)
                ledger.trades.append(
                    FullFlowTrade(
                        variant=variant,
                        signal_ts_open=float(frame.bars[0].ts_open),
                        prefilter=prefilter,
                        fast_screen=fast_screen,
                        pipeline=pipeline,
                        simulation=simulation,
                    )
                )

                if self._config.single_active_position and simulation.entry_triggered:
                    entry_offset = simulation.entry_bar_index or 0
                    next_eligible_index[variant] = max(
                        next_eligible_index[variant],
                        as_of_index + 1 + entry_offset + max(1, simulation.bars_held),
                    )

        return FullFlowComparison(
            symbol=symbol,
            timeframe=timeframe,
            window_bars=window,
            candidate_timestamps=tuple(candidate_timestamps),
            price_only=ledgers["price_only"].summarize(),
            volume_assisted=ledgers["volume_assisted"].summarize(),
        )

    def _screen(
        self,
        frame: KlineFrame,
        prefilter: PrefilterResult,
        variant: ExperimentVariant,
        volume_context: VolumePriceContext | None,
    ) -> FastScreenResult:
        key = _cache_key(
            stage="fast_screen",
            frame=frame,
            variant=variant,
            volume_context=volume_context,
            prefilter=prefilter,
            config=self._config,
        )
        cached = self._cache.get("fast_screen", key) if self._cache is not None else None
        if cached is not None:
            return FastScreenResult.from_payload(cached)
        result = self._fast_screener.screen(
            frame=frame,
            prefilter=prefilter,
            volume_context=volume_context,
        )
        if self._cache is not None:
            self._cache.put("fast_screen", key, result.to_payload())
        return result

    def _run_pipeline(
        self,
        frame: KlineFrame,
        prefilter: PrefilterResult,
        variant: ExperimentVariant,
        volume_context: VolumePriceContext | None,
    ) -> PipelineResult:
        key = _cache_key(
            stage="full_pipeline",
            frame=frame,
            variant=variant,
            volume_context=volume_context,
            prefilter=prefilter,
            config=self._config,
        )
        cached = self._cache.get("full_pipeline", key) if self._cache is not None else None
        if cached is not None:
            return PipelineResult.from_payload(cached)
        result = self._pipeline.run(
            frame=frame,
            variant=variant,
            volume_context=volume_context,
        )
        if self._cache is not None:
            self._cache.put("full_pipeline", key, result.to_payload())
        return result


class _VariantLedger:
    """Mutable accumulator kept private so public backtest results stay immutable."""

    def __init__(self, variant: ExperimentVariant) -> None:
        self.variant = variant
        self.logic_candidates = 0
        self.screened_out = 0
        self.full_pipeline_runs = 0
        self.pipeline_failures = 0
        self.skipped_active_position = 0
        self.simulations: list[TradeSimulation] = []
        self.usage_total: dict[str, int] = {}
        self.latency_ms = 0.0
        self.trades: list[FullFlowTrade] = []

    def summarize(self) -> FullFlowSummary:
        metrics = calculate_metrics(self.simulations)
        total_r = sum(
            result.r_multiple
            for result in self.simulations
            if result.entry_triggered and result.status not in {"invalid", "skipped", "not_triggered"}
        )
        return FullFlowSummary(
            variant=self.variant,
            logic_candidates=self.logic_candidates,
            screened_out=self.screened_out,
            full_pipeline_runs=self.full_pipeline_runs,
            pipeline_failures=self.pipeline_failures,
            skipped_active_position=self.skipped_active_position,
            simulations=tuple(self.simulations),
            metrics=metrics,
            total_r=float(total_r),
            usage_total=dict(self.usage_total),
            latency_ms=self.latency_ms,
            trades=tuple(self.trades),
        )
