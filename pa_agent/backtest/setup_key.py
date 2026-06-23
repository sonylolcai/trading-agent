"""Setup key construction for historical win-rate buckets."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class SetupKey:
    symbol_class: str
    timeframe_bucket: str
    cycle_position: str
    direction: str
    order_type: str
    primary_patterns: tuple[str, ...]
    decision_stance: str

    def as_string(self) -> str:
        patterns = "+".join(self.primary_patterns) if self.primary_patterns else "none"
        return "|".join(
            (
                self.symbol_class,
                self.timeframe_bucket,
                self.cycle_position,
                self.direction,
                self.order_type,
                patterns,
                self.decision_stance,
            )
        )


def classify_symbol(symbol: object) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return "unknown"
    if re.fullmatch(r"(SH|SZ)?\d{6}", text):
        return "a_share"
    if any(token in text for token in ("BTC", "ETH", "USDT", "USDTPERP")):
        return "crypto"
    if text.startswith(("XAU", "XAG")) or re.fullmatch(r"[A-Z]{6}", text):
        return "forex"
    return "other"


def bucket_timeframe(timeframe: object) -> str:
    text = str(timeframe or "").strip().lower()
    if not text:
        return "unknown"
    if text.endswith("m") or text.endswith("min"):
        return "intraday_minute"
    if text.endswith("h"):
        return "intraday_hour"
    if text in {"d", "1d", "day", "daily"}:
        return "daily"
    if text in {"w", "1w", "week", "weekly"}:
        return "weekly"
    return text


def normalize_patterns(patterns: Iterable[object] | None, *, limit: int = 3) -> tuple[str, ...]:
    values = []
    for pattern in patterns or []:
        text = str(pattern or "").strip().lower()
        if not text:
            continue
        values.append(re.sub(r"\s+", "_", text))
    return tuple(sorted(dict.fromkeys(values))[:limit])


def _decision_dict(stage2_decision: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(stage2_decision, dict):
        return {}
    nested = stage2_decision.get("decision")
    if isinstance(nested, dict):
        return nested
    return stage2_decision


def build_setup_key(
    *,
    symbol: object,
    timeframe: object,
    stage1_diagnosis: dict[str, Any] | None,
    stage2_decision: dict[str, Any] | None,
    decision_stance: str = "conservative",
) -> SetupKey:
    """Build the statistical bucket for a Stage 2 setup."""
    stage1 = stage1_diagnosis or {}
    decision = _decision_dict(stage2_decision)
    patterns = stage1.get("detected_patterns")
    if not patterns:
        patterns = stage1.get("patterns")
    return SetupKey(
        symbol_class=classify_symbol(symbol),
        timeframe_bucket=bucket_timeframe(timeframe),
        cycle_position=str(stage1.get("cycle_position") or "unknown"),
        direction=str(decision.get("order_direction") or stage1.get("direction") or "unknown"),
        order_type=str(decision.get("order_type") or "unknown"),
        primary_patterns=normalize_patterns(patterns),
        decision_stance=str(decision_stance or "conservative"),
    )
