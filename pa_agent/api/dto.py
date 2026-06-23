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
                masked[key] = mask_secret(str(child or ""))
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
        "ts_open": bar.ts_open,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "amount": bar.amount,
        "pct_chg": bar.pct_chg,
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
        "path": str(path),
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
