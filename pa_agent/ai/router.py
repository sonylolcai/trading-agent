"""Strategy file router — maps Stage 1 diagnosis to strategy file list.

Implements 使用说明 §11 routing table exactly.
This is a pure function: no side effects, no external state.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── File name constants ────────────────────────────────────────────────────────

_BULLISH_CHANNEL_FILES = [
    "上涨通道分析识别.txt",
    "上涨通道交易策略.txt",
]
_BEARISH_CHANNEL_FILES = [
    "下跌通道分析识别.txt",
    "下跌通道交易策略.txt",
]
_CHANNEL_WIDTH_FILE = "文件13-窄通道与宽通道策略.txt"

_BULLISH_SPIKE_FILES = [
    "极速上涨分析识别.txt",
    "极速上涨交易策略.txt",
]
_BEARISH_SPIKE_FILES = [
    "极速下跌分析识别.txt",
    "极速下跌交易策略.txt",
]

_RANGE_FILES = [
    "震荡区间分析识别.txt",
    "震荡区间交易策略.txt",
]

_WEDGE_FILE = "文件14-楔形形态分析交易.txt"
_REVERSAL_FILE = "文件15-二次入场机会.txt"

# All 17 valid file names (used for dedup validation)
_ALL_VALID_FILES: frozenset[str] = frozenset([
    "提示词大纲_人设与思维方式.txt",
    "市场诊断框架.txt",
    "文件16-K线信号识别.txt",
    "文件17-止损和止盈与仓位管理.txt",
    "上涨通道分析识别.txt",
    "上涨通道交易策略.txt",
    "文件13-窄通道与宽通道策略.txt",
    "下跌通道分析识别.txt",
    "下跌通道交易策略.txt",
    "极速上涨分析识别.txt",
    "极速上涨交易策略.txt",
    "极速下跌分析识别.txt",
    "极速下跌交易策略.txt",
    "震荡区间分析识别.txt",
    "震荡区间交易策略.txt",
    "文件14-楔形形态分析交易.txt",
    "文件15-二次入场机会.txt",
])

_CHANNEL_STATES = frozenset(["micro_channel", "tight_channel", "normal_channel", "broad_channel"])
_RANGE_STATES = frozenset(["trading_range", "trending_tr"])
_SKIP_STATES = frozenset(["extreme_tr", "unknown"])


def route_strategy_files(stage1_json: dict[str, Any]) -> list[str]:
    """Return the ordered, deduplicated list of strategy files for Stage 2.

    Args:
        stage1_json: The validated Stage 1 diagnosis JSON object.

    Returns:
        List of file names to load, in the order they should appear in the
        Stage 2 system prompt. Always a subset of the 17 known files.
        Empty list means "do not trade" (extreme_tr / unknown).
    """
    cp = stage1_json.get("cycle_position", "unknown")
    direction = stage1_json.get("direction", "neutral")
    patterns = stage1_json.get("detected_patterns", []) or []

    files: list[str] = []

    # ── Channel states ────────────────────────────────────────────────────────
    if cp in _CHANNEL_STATES:
        if direction == "bullish":
            files.extend(_BULLISH_CHANNEL_FILES)
        elif direction == "bearish":
            files.extend(_BEARISH_CHANNEL_FILES)
        else:
            logger.warning(
                "Channel state %r with neutral direction — no directional strategy files loaded", cp
            )
        files.append(_CHANNEL_WIDTH_FILE)

    # ── Spike state ───────────────────────────────────────────────────────────
    elif cp == "spike":
        if direction == "bullish":
            files.extend(_BULLISH_SPIKE_FILES)
        elif direction == "bearish":
            files.extend(_BEARISH_SPIKE_FILES)
        else:
            logger.warning("Spike with neutral direction — no spike strategy files loaded")

    # ── Range states ──────────────────────────────────────────────────────────
    elif cp in _RANGE_STATES:
        files.extend(_RANGE_FILES)

    # ── Skip states (extreme_tr / unknown) ────────────────────────────────────
    elif cp in _SKIP_STATES:
        pass  # no strategy files — do not trade

    else:
        logger.warning("Unknown cycle_position %r — no strategy files loaded", cp)

    # ── Pattern overlays ──────────────────────────────────────────────────────
    if "wedge" in patterns:
        files.append(_WEDGE_FILE)
    if "reversal_attempt" in patterns:
        files.append(_REVERSAL_FILE)

    # ── Stable dedup (preserve first occurrence) ──────────────────────────────
    seen: set[str] = set()
    deduped: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            deduped.append(f)

    return deduped
