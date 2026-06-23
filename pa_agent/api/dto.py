"""DTO helpers for the local PA Agent Web API."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from pa_agent.config.settings import Settings
from pa_agent.data.base import KlineBar, KlineFrame
from pa_agent.records.schema import AnalysisRecord
from pa_agent.util.mask_secret import mask_secret

SECRET_KEYS = {
    "api_key",
    "api_key_encrypted",
    "secret",
    "app_secret",
    "token",
    "webhook_url",
}


def _mask_api_secret(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 4:
        return "***"
    return mask_secret(text)


def _json_float(value: float) -> float | None:
    if math.isnan(value) or math.isinf(value):
        return None
    return float(value)


def _mask_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, child in value.items():
            if key == "api_key_encrypted":
                continue
            if key in SECRET_KEYS:
                masked[key] = _mask_api_secret(child)
            else:
                masked[key] = _mask_mapping(child)
        return masked
    if isinstance(value, list):
        return [_mask_mapping(item) for item in value]
    return value


def settings_to_payload(settings: Settings) -> dict[str, Any]:
    """Return settings as JSON-safe data with secrets masked."""
    return _mask_mapping(settings.model_dump())


def bar_to_payload(bar: KlineBar) -> dict[str, Any]:
    """Return a JSON-safe representation of one K-line bar."""
    return {
        "seq": bar.seq,
        "ts_open": _json_float(bar.ts_open),
        "open": _json_float(bar.open),
        "high": _json_float(bar.high),
        "low": _json_float(bar.low),
        "close": _json_float(bar.close),
        "volume": _json_float(bar.volume),
        "amount": _json_float(bar.amount),
        "pct_chg": None if bar.pct_chg is None else _json_float(bar.pct_chg),
        "closed": bar.closed,
    }


def frame_to_payload(frame: KlineFrame) -> dict[str, Any]:
    """Return a JSON-safe frame payload while preserving newest-first bars."""
    return {
        "symbol": frame.symbol,
        "timeframe": frame.timeframe,
        "order": "newest_first",
        "snapshot_ts_local_ms": frame.snapshot_ts_local_ms,
        "bars": [bar_to_payload(bar) for bar in frame.bars],
        "indicators": {
            "ema20": [_json_float(value) for value in frame.indicators.ema20],
            "atr14": [_json_float(value) for value in frame.indicators.atr14],
        },
    }


def record_summary_to_payload(path: Path, record: AnalysisRecord) -> dict[str, Any]:
    """Return the compact row shown by the Web history page."""
    decision = record.stage2_decision or {}
    action = decision.get("action") or decision.get("order_type") or ""
    direction = decision.get("direction") or ""
    return {
        "id": path.stem,
        "timestamp_local_iso": record.meta.timestamp_local_iso,
        "timestamp_local_ms": record.meta.timestamp_local_ms,
        "symbol": record.meta.symbol,
        "timeframe": record.meta.timeframe,
        "bar_count": record.meta.bar_count,
        "decision_stance": record.meta.decision_stance,
        "action": action,
        "direction": direction,
        "has_exception": record.exception is not None,
    }
