"""Deterministic, as-of-bar volume context for research A/B runs.

The production PA workflow is deliberately price-action led.  This module does
not create an entry signal or veto a trade: it derives a small, auditable set
of volume facts from the latest closed bar and the bars that existed before it.
Callers may pass the rendered block to an experimental prompt variant while the
baseline workflow remains byte-for-byte free of this supplemental context.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from pa_agent.data.base import KlineBar, KlineFrame


VOLUME_LOOKBACK_BARS = 20
VOLUME_EXPANSION_RATIO = 1.5
VOLUME_SPIKE_RATIO = 1.8
STRONG_CLOSE_POSITION = 0.7
WEAK_CLOSE_LOWER_POSITION = 0.35
WEAK_CLOSE_UPPER_POSITION = 0.65


@dataclass(frozen=True)
class VolumePriceContext:
    """Facts calculated strictly from the analysis snapshot.

    ``latest_volume`` belongs to K1. ``average_volume`` uses K2 through K21,
    never a later bar.  This explicit separation makes the context safe for
    bar-by-bar historical replay and straightforward to audit from a record.
    """

    available: bool
    lookback_bars: int
    reference_bar_count: int
    latest_volume: float | None
    average_volume: float | None
    relative_volume: float | None
    close_position: float | None
    condition: str
    note: str

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-safe snapshot suitable for records and cache keys."""
        return asdict(self)

    def to_prompt_block(self) -> str:
        """Render the research-only instruction shared by the fast and full LLMs."""
        if not self.available:
            return (
                "## 量价辅助上下文（A/B 研究组）\n\n"
                "当前 K 线不足以形成可比的成交量基准，或成交量为零。"
                "本轮完全按原有价格行为逻辑判断，不得由成交量补充推断。\n"
            )

        return (
            "## 量价辅助上下文（A/B 研究组，只读）\n\n"
            "这是程序在当前分析时点预先计算的事实：K1 的成交量与 K2-K21 的均量比较；"
            "不含未来 K 线。价格行为仍是主导依据，成交量只能辅助确认或提示谨慎，"
            "不得单独构成入场、否决既有价格结构，或替代原有风控/决策树。\n\n"
            f"- K1 成交量：{self.latest_volume:.0f}\n"
            f"- K2-K{self.reference_bar_count + 1} 平均成交量：{self.average_volume:.0f}\n"
            f"- 相对量能（K1 / 均量）：{self.relative_volume:.2f}x\n"
            f"- K1 收盘在自身区间的位置：{self.close_position:.0%}\n"
            f"- 程序标签：{self.condition}\n"
            f"- 使用说明：{self.note}\n\n"
            "若价格结构、跟随和交易者方程不成立，不能因量能而放宽；"
            "若价格结构已成立，可将量能用于置信度的微调，或在放量但收盘疲弱时提高等待门槛。\n"
        )


def _closed_newest_first(bars: Iterable[KlineBar]) -> list[KlineBar]:
    """Return closed bars in the frame's canonical newest-first ordering."""
    return [bar for bar in bars if bool(getattr(bar, "closed", True))]


def build_volume_price_context(
    frame: KlineFrame,
    *,
    lookback_bars: int = VOLUME_LOOKBACK_BARS,
) -> VolumePriceContext:
    """Create an immutable volume context using only information in *frame*.

    The caller is responsible for making ``frame`` an as-of snapshot.  The
    function intentionally has no dependency on direction, future bars, order
    type, or outcome, preventing it from becoming a hidden trading rule.
    """
    closed = _closed_newest_first(frame.bars)
    required = max(1, int(lookback_bars))
    latest = closed[0] if closed else None
    reference = closed[1 : required + 1]
    latest_volume = float(latest.volume) if latest is not None else None

    if latest is None or len(reference) < required:
        return VolumePriceContext(
            available=False,
            lookback_bars=required,
            reference_bar_count=len(reference),
            latest_volume=latest_volume,
            average_volume=None,
            relative_volume=None,
            close_position=None,
            condition="unavailable",
            note="历史成交量样本不足，回退为纯价格行为判断。",
        )

    reference_volumes = [max(0.0, float(bar.volume)) for bar in reference]
    average_volume = sum(reference_volumes) / len(reference_volumes)
    price_range = float(latest.high) - float(latest.low)
    if latest_volume is None or latest_volume <= 0 or average_volume <= 0 or price_range <= 0:
        return VolumePriceContext(
            available=False,
            lookback_bars=required,
            reference_bar_count=len(reference),
            latest_volume=latest_volume,
            average_volume=average_volume if average_volume > 0 else None,
            relative_volume=None,
            close_position=None,
            condition="unavailable",
            note="成交量或 K1 振幅不可比，回退为纯价格行为判断。",
        )

    relative_volume = latest_volume / average_volume
    close_position = (float(latest.close) - float(latest.low)) / price_range
    if relative_volume >= VOLUME_SPIKE_RATIO and (
        WEAK_CLOSE_LOWER_POSITION <= close_position <= WEAK_CLOSE_UPPER_POSITION
    ):
        condition = "high_volume_weak_close"
        note = "显著放量但收盘未靠近极点，警惕衰竭或双方分歧；需更严格的价格确认。"
    elif relative_volume >= VOLUME_EXPANSION_RATIO and close_position >= STRONG_CLOSE_POSITION:
        condition = "expanded_volume_strong_close"
        note = "放量且收盘接近高点；仅在价格结构本身成立时可作多头辅助确认。"
    elif relative_volume >= VOLUME_EXPANSION_RATIO and close_position <= 1.0 - STRONG_CLOSE_POSITION:
        condition = "expanded_volume_strong_close"
        note = "放量且收盘接近低点；仅在价格结构本身成立时可作空头辅助确认。"
    elif relative_volume < 0.7:
        condition = "contracted_volume"
        note = "量能低于近期常态；不能据此否定价格结构，仅降低量能确认权重。"
    else:
        condition = "neutral"
        note = "量能未给出明显增量信息，按原有价格行为逻辑判断。"

    return VolumePriceContext(
        available=True,
        lookback_bars=required,
        reference_bar_count=len(reference),
        latest_volume=latest_volume,
        average_volume=average_volume,
        relative_volume=relative_volume,
        close_position=close_position,
        condition=condition,
        note=note,
    )
