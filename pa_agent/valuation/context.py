"""Auditable A-share valuation context.

This module intentionally produces a small, deterministic snapshot.  It does
not create trade signals, call an LLM, or turn a current valuation quote into a
claim about historical alpha.  The snapshot is attached to an analysis record
so a later review can see exactly what supplemental data the model received.
"""
from __future__ import annotations

import math
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

_A_SHARE_CODE = re.compile(r"(?:^|[^0-9])([0-9]{6})(?:$|[^0-9])")


@dataclass(frozen=True)
class ValuationContext:
    """A point-in-time, non-binding valuation and financial-quality snapshot."""

    available: bool
    symbol: str
    source: str
    fetched_at_ms: int
    data_quality: str
    valuation_level: str
    valuation_score: int | None
    quality_level: str
    quality_score: int | None
    growth_level: str
    growth_score: int | None
    metrics: dict[str, float]
    risk_flags: tuple[str, ...]
    note: str

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["risk_flags"] = list(self.risk_flags)
        return payload

    def to_prompt_block(self) -> str:
        """Render the supplemental context without granting it signal authority."""
        if not self.available:
            return (
                "## 价值快照（程序计算，只读）\n\n"
                "当前标的不是可识别的 A 股，或估值/财务字段不足。本轮严格按既有价格行为流程判断；"
                "不得补造价值结论。\n"
            )

        metric_lines = []
        labels = {
            "pe_dynamic": "动态 PE",
            "pb": "PB",
            "roe": "加权 ROE",
            "debt_to_asset": "资产负债率",
            "net_profit_yoy": "净利润同比",
        }
        for key in ("pe_dynamic", "pb", "roe", "debt_to_asset", "net_profit_yoy"):
            value = self.metrics.get(key)
            if value is None:
                continue
            suffix = "%" if key in {"roe", "debt_to_asset", "net_profit_yoy"} else ""
            metric_lines.append(f"- {labels[key]}：{value:.2f}{suffix}")
        metrics_block = "\n".join(metric_lines) or "- 可用指标不足"
        flags = "、".join(self.risk_flags) if self.risk_flags else "无程序标记"
        return (
            "## 价值快照（程序计算，只读）\n\n"
            "这是本次请求时抓取并按固定规则归纳的 A 股补充信息，不含未来数据，也不是买卖信号。"
            "价格行为、结构、止损和交易者方程仍是短线决策的唯一主链路；"
            "价值层只能补充中长线风险、持仓倾向和需要核验的事项，不能单独否决或建立交易。\n\n"
            f"- 数据质量：{self.data_quality}\n"
            f"- 估值：{self.valuation_level}（分数：{self.valuation_score if self.valuation_score is not None else '未知'}）\n"
            f"- 财务质量：{self.quality_level}（分数：{self.quality_score if self.quality_score is not None else '未知'}）\n"
            f"- 增长：{self.growth_level}（分数：{self.growth_score if self.growth_score is not None else '未知'}）\n"
            f"- 风险标记：{flags}\n"
            f"{metrics_block}\n"
            f"- 使用说明：{self.note}\n"
        )


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _extract_ashare_code(symbol: str) -> str | None:
    match = _A_SHARE_CODE.search(str(symbol or "").strip())
    return match.group(1) if match else None


def _first_metric(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _as_float(row.get(key))
        if value is not None:
            return value
    return None


def fetch_ashare_valuation_inputs(symbol: str) -> dict[str, Any]:
    """Fetch the minimal live inputs required for one A-share snapshot.

    Data-provider failures deliberately stay local to their individual fields:
    a quote-only snapshot remains useful, but clearly partial.
    """
    from pa_agent.data.eastmoney_extended import (
        datacenter_for_symbol,
        fetch_valuation_summary,
    )

    code = _extract_ashare_code(symbol)
    if code is None:
        return {}
    summary = fetch_valuation_summary(code) or {}
    try:
        finance_rows = datacenter_for_symbol("finance_main", code, page_size=1) or []
    except Exception:  # noqa: BLE001 - provider data is best-effort, never an analysis failure
        finance_rows = []
    finance = finance_rows[0] if finance_rows and isinstance(finance_rows[0], dict) else {}
    return {
        "pe_dynamic": summary.get("pe_dynamic"),
        "pb": summary.get("pb"),
        "total_mv": summary.get("total_mv"),
        "roe": _first_metric(finance, "WEIGHT_ROE", "ROE_WEIGHTED", "ROEJQ", "ROE"),
        "debt_to_asset": _first_metric(
            finance, "DEBT_ASSET_RATIO", "ASSET_LIAB_RATIO", "DEBT_TO_ASSET"
        ),
        "net_profit_yoy": _first_metric(
            finance, "NETPROFIT_YOY_RATIO", "NETPROFIT_YOY", "NET_PROFIT_YOY"
        ),
    }


def _score_valuation(pe: float | None, pb: float | None) -> tuple[str, int | None, list[str]]:
    flags: list[str] = []
    score_parts: list[int] = []
    if pe is not None:
        if pe <= 0:
            flags.append("盈利为负或动态 PE 不适用")
        elif pe <= 15:
            score_parts.append(20)
        elif pe <= 30:
            score_parts.append(8)
        elif pe <= 50:
            score_parts.append(0)
        else:
            score_parts.append(-18)
            flags.append("动态 PE 较高")
    if pb is not None:
        if pb <= 1.2:
            score_parts.append(15)
        elif pb <= 3:
            score_parts.append(5)
        elif pb <= 6:
            score_parts.append(0)
        else:
            score_parts.append(-12)
            flags.append("PB 较高")
    if not score_parts:
        return "unknown", None, flags
    score = max(0, min(100, 50 + sum(score_parts)))
    level = "cheap" if score >= 65 else "expensive" if score <= 38 else "fair"
    return level, score, flags


def _score_quality(roe: float | None, debt: float | None) -> tuple[str, int | None, list[str]]:
    flags: list[str] = []
    score_parts: list[int] = []
    if roe is not None:
        if roe >= 15:
            score_parts.append(20)
        elif roe >= 10:
            score_parts.append(10)
        elif roe < 5:
            score_parts.append(-15)
            flags.append("ROE 偏低")
    if debt is not None:
        if debt <= 40:
            score_parts.append(15)
        elif debt <= 60:
            score_parts.append(7)
        elif debt > 75:
            score_parts.append(-15)
            flags.append("资产负债率偏高")
    if not score_parts:
        return "unknown", None, flags
    score = max(0, min(100, 50 + sum(score_parts)))
    level = "strong" if score >= 65 else "weak" if score <= 35 else "neutral"
    return level, score, flags


def _score_growth(net_profit_yoy: float | None) -> tuple[str, int | None, list[str]]:
    if net_profit_yoy is None:
        return "unknown", None, []
    if net_profit_yoy >= 20:
        return "strong", 70, []
    if net_profit_yoy >= 0:
        return "neutral", 55, []
    return "weak", 30, ["净利润同比为负"]


def build_valuation_context(
    symbol: str,
    *,
    fetcher: Callable[[str], dict[str, Any]] = fetch_ashare_valuation_inputs,
    now_ms: int | None = None,
) -> ValuationContext:
    """Build an A-share-only snapshot and degrade safely on any provider issue."""
    fetched_at_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    code = _extract_ashare_code(symbol)
    if code is None:
        return ValuationContext(
            available=False, symbol=str(symbol), source="none", fetched_at_ms=fetched_at_ms,
            data_quality="not_applicable", valuation_level="unknown", valuation_score=None,
            quality_level="unknown", quality_score=None, growth_level="unknown", growth_score=None,
            metrics={}, risk_flags=(), note="仅 A 股六码代码启用价值快照。",
        )
    try:
        raw = fetcher(code) or {}
    except Exception:  # noqa: BLE001 - a provider failure must not fail the analysis
        raw = {}
    metrics = {
        key: value
        for key in ("pe_dynamic", "pb", "roe", "debt_to_asset", "net_profit_yoy")
        if (value := _as_float(raw.get(key))) is not None
    }
    if not metrics:
        return ValuationContext(
            available=False, symbol=code, source="eastmoney", fetched_at_ms=fetched_at_ms,
            data_quality="unavailable", valuation_level="unknown", valuation_score=None,
            quality_level="unknown", quality_score=None, growth_level="unknown", growth_score=None,
            metrics={}, risk_flags=(), note="数据源未返回可用估值或财务字段，已回退为价格行为分析。",
        )
    valuation_level, valuation_score, valuation_flags = _score_valuation(
        metrics.get("pe_dynamic"), metrics.get("pb")
    )
    quality_level, quality_score, quality_flags = _score_quality(
        metrics.get("roe"), metrics.get("debt_to_asset")
    )
    growth_level, growth_score, growth_flags = _score_growth(metrics.get("net_profit_yoy"))
    data_quality = "complete" if len(metrics) >= 4 else "partial"
    return ValuationContext(
        available=True,
        symbol=code,
        source="eastmoney",
        fetched_at_ms=fetched_at_ms,
        data_quality=data_quality,
        valuation_level=valuation_level,
        valuation_score=valuation_score,
        quality_level=quality_level,
        quality_score=quality_score,
        growth_level=growth_level,
        growth_score=growth_score,
        metrics=metrics,
        risk_flags=tuple(dict.fromkeys(valuation_flags + quality_flags + growth_flags)),
        note="价值层仅提供中长线风险与持仓倾向参考，不改变既有短线价格行为信号。",
    )
