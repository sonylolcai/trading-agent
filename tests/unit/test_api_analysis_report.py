from __future__ import annotations

from typing import Any

from pa_agent.api.dto import analysis_record_to_payload
from pa_agent.records.schema import AnalysisRecord, RecordMeta


def _record(
    *,
    stage1_diagnosis: dict[str, Any] | None,
    stage2_decision: dict[str, Any] | None,
) -> AnalysisRecord:
    return AnalysisRecord(
        meta=RecordMeta(
            timestamp_local_iso="2026-06-23T12:00:00.000",
            timestamp_local_ms=1_781_000_000_000,
            symbol="000001",
            timeframe="1h",
            bar_count=20,
            ai_provider={},
            decision_stance="balanced",
            decision_confidence_threshold=40,
        ),
        kline_data=[],
        htf_text="",
        stage1_messages=[],
        stage1_response=None,
        stage1_diagnosis=stage1_diagnosis,
        stage2_messages=[],
        stage2_response=None,
        stage2_decision=stage2_decision,
        strategy_files_used=[],
        experience_loaded=[],
        exception=None,
        usage_total={},
    )


def test_analysis_payload_includes_frontend_friendly_report() -> None:
    stage1 = {
        "cycle_position": "normal_channel",
        "direction": "bullish",
        "diagnosis_confidence": 76,
        "key_signals": ["K2 strong signal"],
        "watch_points": ["K1 follow-through"],
        "bar_by_bar_summary": [
            {
                "bar": "K1",
                "role": "signal",
                "bar_type": "trend_bull",
                "context_effect": "strengthens_bull",
                "reason": "K1 closes near the high.",
            }
        ],
        "gate_trace": [
            {
                "node_id": "1.1",
                "section": "preflight",
                "question": "Enough bars?",
                "answer": "是",
                "reason": "20 closed bars are available.",
                "bar_range": "K20-K1",
                "skipped": False,
            }
        ],
    }
    stage2 = {
        "decision": {
            "order_type": "突破单",
            "order_direction": "做多",
            "entry_price": 2010.5,
            "take_profit_price": 2050.0,
            "stop_loss_price": 1995.0,
            "reasoning": "Breakout has follow-through.",
            "trade_confidence": 72,
            "estimated_win_rate": 58,
            "historical_win_rate_for_this_setup": 66,
            "historical_sample_count": 18,
            "historical_expectancy_r": 0.42,
            "key_factors": ["trend alignment"],
            "watch_points": ["failed breakout"],
            "risk_assessment": "False breakout risk.",
        },
        "decision_trace": [
            {
                "node_id": "9.1",
                "section": "signal bar",
                "question": "Valid signal bar?",
                "answer": "是",
                "reason": "Signal bar is strong.",
                "bar_range": "K2",
                "skipped": False,
            }
        ],
        "terminal": {
            "node_id": "11.2",
            "outcome": "trade",
            "label": "Place breakout order",
        },
        "next_bar_prediction": {
            "direction": "bullish",
            "probabilities": {"bullish": 60, "bearish": 25, "neutral": 15},
            "reasoning": "Momentum favors another bullish bar.",
        },
        "next_cycle_prediction": {
            "cycle": "normal_channel",
            "direction": "bullish",
            "probabilities": {"normal_channel": 70, "trading_range": 30},
            "reasoning": "Channel is still intact.",
        },
    }

    payload = analysis_record_to_payload(
        _record(stage1_diagnosis=stage1, stage2_decision=stage2)
    )

    assert payload["stage1_diagnosis"] == stage1
    assert payload["stage2_decision"] == stage2
    assert payload["decision_stance"] == "balanced"
    assert payload["decision_confidence_threshold"] == 40

    report = payload["analysis_report"]
    assert report["headline"] == {
        "action": "突破单",
        "direction": "做多",
        "summary": "Breakout has follow-through.",
        "risk": "False breakout risk.",
    }
    assert {"label": "交易信心", "value": 72, "unit": "%", "tone": "good"} in report[
        "metrics"
    ]
    assert {"label": "历史胜率", "value": 66, "unit": "%", "tone": "good"} in report[
        "metrics"
    ]
    assert {"label": "历史样本", "value": 18, "unit": "", "tone": "neutral"} in report[
        "metrics"
    ]
    assert {"label": "历史期望R", "value": 0.42, "unit": "R", "tone": "neutral"} in report[
        "metrics"
    ]
    assert report["decision"] == {
        "order_type": "突破单",
        "direction": "做多",
        "risk_profile": "balanced",
        "signal_threshold": 40,
        "entry_price": 2010.5,
        "stop_loss_price": 1995.0,
        "take_profit_price": 2050.0,
        "terminal": stage2["terminal"],
    }
    assert report["evidence_tables"][0]["title"] == "阶段一闸门判断"
    assert report["evidence_tables"][0]["rows"] == [
        {
            "node_id": "1.1",
            "section": "preflight",
            "question": "Enough bars?",
            "answer": "是",
            "reason": "20 closed bars are available.",
            "bar_range": "K20-K1",
            "skipped": False,
        }
    ]
    assert report["evidence_tables"][1]["title"] == "阶段二决策路径"
    assert report["evidence_tables"][1]["rows"][0]["question"] == "Valid signal bar?"
    assert report["flows"] == [
        {
            "title": "逐K线结构流程",
            "items": [
                {
                    "id": "K1",
                    "label": "signal",
                    "value": "trend_bull",
                    "detail": "K1 closes near the high.",
                    "tone": "good",
                }
            ],
        }
    ]
    assert report["probability_blocks"][0] == {
        "title": "下一根K线预测",
        "items": [
            {"label": "bullish", "value": 60},
            {"label": "bearish", "value": 25},
            {"label": "neutral", "value": 15},
        ],
        "reasoning": "Momentum favors another bullish bar.",
    }
    assert report["probability_blocks"][1]["items"] == [
        {"label": "normal_channel", "value": 70},
        {"label": "trading_range", "value": 30},
    ]
    assert report["lists"] == [
        {"title": "关键因素", "items": ["trend alignment"]},
        {"title": "观察点", "items": ["failed breakout"]},
    ]


def test_analysis_report_returns_empty_structures_for_missing_or_odd_stage_shapes() -> None:
    payload = analysis_record_to_payload(
        _record(
            stage1_diagnosis=None,
            stage2_decision={
                "decision": None,
                "decision_trace": "not-a-list",
                "next_bar_prediction": {
                    "probabilities": None,
                    "reasoning": "Too noisy to predict.",
                },
                "next_cycle_prediction": None,
            },
        )
    )

    report = payload["analysis_report"]

    assert report["headline"] == {
        "action": "不下单",
        "direction": None,
        "summary": "",
        "risk": "",
    }
    assert report["decision"] == {
        "order_type": "不下单",
        "direction": None,
        "risk_profile": "balanced",
        "signal_threshold": 40,
        "entry_price": None,
        "stop_loss_price": None,
        "take_profit_price": None,
        "terminal": {},
    }
    assert report["metrics"] == []
    assert report["evidence_tables"][0]["rows"] == []
    assert report["evidence_tables"][1]["rows"] == []
    assert report["flows"] == [{"title": "逐K线结构流程", "items": []}]
    assert report["probability_blocks"][0] == {
        "title": "下一根K线预测",
        "items": [],
        "reasoning": "Too noisy to predict.",
    }
    assert report["probability_blocks"][1] == {
        "title": "下一周期预测",
        "items": [],
        "reasoning": "",
    }
    assert report["lists"] == [
        {"title": "关键因素", "items": []},
        {"title": "观察点", "items": []},
    ]


def test_analysis_report_preserves_zero_metric_values() -> None:
    payload = analysis_record_to_payload(
        _record(
            stage1_diagnosis={"diagnosis_confidence": 0},
            stage2_decision={
                "decision": {
                    "order_type": "不下单",
                    "trade_confidence": 0,
                    "estimated_win_rate": 0,
                    "historical_sample_count": 0,
                }
            },
        )
    )

    assert payload["analysis_report"]["metrics"] == [
        {"label": "诊断信心", "value": 0, "unit": "%", "tone": "bad"},
        {"label": "交易信心", "value": 0, "unit": "%", "tone": "bad"},
        {"label": "预估胜率", "value": 0, "unit": "%", "tone": "bad"},
        {"label": "历史样本", "value": 0, "unit": "", "tone": "neutral"},
    ]
