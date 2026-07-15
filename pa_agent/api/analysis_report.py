"""Presentation-focused analysis report payloads for the Web API."""
from __future__ import annotations

from typing import Any

from pa_agent.records.schema import AnalysisRecord


def build_analysis_report(record: AnalysisRecord) -> dict[str, Any]:
    """Return a stable, frontend-friendly report for an analysis record."""
    stage1 = _as_dict(record.stage1_diagnosis)
    stage2 = _as_dict(record.stage2_decision)
    decision = _decision_dict(stage2)
    terminal = _as_dict(stage2.get("terminal"))
    risk_profile = record.meta.decision_stance
    signal_threshold = record.meta.decision_confidence_threshold

    action = _first_text(
        decision.get("action"),
        decision.get("order_type"),
        stage2.get("action"),
        stage2.get("order_type"),
    ) or "不下单"
    direction = _first_optional_text(
        decision.get("direction"),
        decision.get("order_direction"),
        decision.get("trade_direction"),
        stage2.get("direction"),
    )
    summary = _first_text(
        decision.get("reasoning"),
        stage2.get("reasoning"),
        stage2.get("summary"),
        terminal.get("label"),
    )
    risk = _first_text(
        decision.get("risk_assessment"),
        stage2.get("risk_assessment"),
        stage1.get("risk_warning"),
    )

    return {
        "headline": {
            "action": action,
            "direction": direction,
            "summary": summary,
            "risk": risk,
        },
        "metrics": _metrics(stage1, stage2, decision),
        "decision": {
            "order_type": action,
            "direction": direction,
            "risk_profile": risk_profile,
            "signal_threshold": signal_threshold,
            "entry_price": _first_value(decision.get("entry_price"), decision.get("entry")),
            "stop_loss_price": _first_value(
                decision.get("stop_loss_price"),
                decision.get("stop_loss"),
            ),
            "take_profit_price": _first_value(
                decision.get("take_profit_price"),
                decision.get("take_profit"),
            ),
            "terminal": terminal,
        },
        "evidence_tables": [
            {
                "title": "阶段一闸门判断",
                "rows": _trace_rows(stage1.get("gate_trace")),
            },
            {
                "title": "阶段二决策路径",
                "rows": _trace_rows(stage2.get("decision_trace")),
            },
        ],
        "flows": [
            {
                "title": "逐K线结构流程",
                "items": _flow_items(stage1.get("bar_by_bar_summary")),
            }
        ],
        "probability_blocks": [
            _probability_block("下一根K线预测", stage2.get("next_bar_prediction")),
            _probability_block("下一周期预测", stage2.get("next_cycle_prediction")),
        ],
        "lists": [
            {
                "title": "关键因素",
                "items": _string_items(
                    decision.get("key_factors")
                    or stage2.get("key_factors")
                    or stage1.get("key_signals")
                ),
            },
            {
                "title": "观察点",
                "items": _string_items(
                    decision.get("watch_points")
                    or stage2.get("watch_points")
                    or stage1.get("watch_points")
                ),
            },
        ],
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _decision_dict(stage2: dict[str, Any]) -> dict[str, Any]:
    nested = stage2.get("decision")
    if isinstance(nested, dict):
        return nested
    decision_keys = {
        "action",
        "order_type",
        "direction",
        "order_direction",
        "trade_direction",
        "entry",
        "entry_price",
        "stop_loss",
        "stop_loss_price",
        "take_profit",
        "take_profit_price",
    }
    if any(key in stage2 for key in decision_keys):
        return stage2
    return {}


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _first_text(*values: Any) -> str:
    value = _first_value(*values)
    return "" if value is None else str(value)


def _first_optional_text(*values: Any) -> str | None:
    text = _first_text(*values)
    return text or None


def _coerce_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return int(number) if number.is_integer() else number
    return None


def _tone_for_number(value: int | float) -> str:
    if value >= 60:
        return "good"
    if value > 0:
        return "warn"
    return "bad"


def _metric(label: str, value: Any, unit: str = "") -> dict[str, Any] | None:
    number = _coerce_number(value)
    if number is None:
        return None
    return {
        "label": label,
        "value": number,
        "unit": unit,
        "tone": _tone_for_number(number) if unit == "%" else "neutral",
    }


def _metrics(
    stage1: dict[str, Any],
    stage2: dict[str, Any],
    decision: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates = [
        _metric(
            "诊断信心",
            _first_value(decision.get("diagnosis_confidence"), stage1.get("diagnosis_confidence")),
            "%",
        ),
        _metric(
            "交易信心",
            _first_value(
                decision.get("trade_confidence"),
                decision.get("confidence"),
                stage2.get("trade_confidence"),
                stage2.get("confidence"),
            ),
            "%",
        ),
        _metric(
            "预估胜率",
            _first_value(decision.get("estimated_win_rate"), stage2.get("estimated_win_rate")),
            "%",
        ),
        _metric(
            "历史胜率",
            _first_value(
                decision.get("historical_win_rate_for_this_setup"),
                stage2.get("historical_win_rate_for_this_setup"),
            ),
            "%",
        ),
        _metric(
            "历史样本",
            _first_value(decision.get("historical_sample_count"), stage2.get("historical_sample_count")),
        ),
        _metric(
            "历史期望R",
            _first_value(decision.get("historical_expectancy_r"), stage2.get("historical_expectancy_r")),
            "R",
        ),
    ]
    return [metric for metric in candidates if metric is not None]


def _trace_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "node_id": _first_text(item.get("node_id")),
                "section": _first_text(item.get("section")),
                "question": _first_text(item.get("question")),
                "answer": _first_text(item.get("answer")),
                "reason": _first_text(item.get("reason")),
                "bar_range": _first_text(item.get("bar_range")),
                "skipped": bool(item.get("skipped", False)),
            }
        )
    return rows


def _flow_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        value_text = _first_text(
            item.get("value"),
            item.get("bar_type"),
            item.get("signal"),
            item.get("context_effect"),
        )
        detail = _first_text(
            item.get("reason"),
            item.get("detail"),
            item.get("context_effect"),
            item.get("follow_through"),
        )
        items.append(
            {
                "id": _flow_id(item, index),
                "label": _first_text(
                    item.get("role"),
                    item.get("label"),
                    item.get("signal"),
                    item.get("bar_type"),
                ),
                "value": value_text,
                "detail": detail,
                "tone": _flow_tone(value_text, detail),
            }
        )
    return items


def _flow_id(item: dict[str, Any], index: int) -> str:
    explicit = _first_text(item.get("id"), item.get("bar"))
    if explicit:
        return explicit
    seq = item.get("seq")
    if seq is not None and seq != "":
        return f"K{seq}"
    return f"K{index}"


def _flow_tone(value: str, detail: str) -> str:
    text = f"{value} {detail}".lower()
    if any(token in text for token in ("bull", "strong", "strengthen", "follow-through")):
        return "good"
    if any(token in text for token in ("bear", "weak", "fail", "risk", "invalid")):
        return "bad"
    if any(token in text for token in ("wait", "pending", "neutral", "range")):
        return "warn"
    return "neutral"


def _probability_block(title: str, value: Any) -> dict[str, Any]:
    prediction = _as_dict(value)
    probabilities = prediction.get("probabilities")
    items = []
    if isinstance(probabilities, dict):
        items = [
            {"label": str(label), "value": probability}
            for label, probability in probabilities.items()
        ]
    return {
        "title": title,
        "items": items,
        "reasoning": _first_text(prediction.get("reasoning")),
    }


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and item != ""]
