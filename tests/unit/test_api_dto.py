from __future__ import annotations

import math

from pa_agent.api.dto import frame_to_payload, record_summary_to_payload, settings_to_payload
from pa_agent.config.settings import Settings
from pa_agent.data.base import IndicatorBundle, KlineBar, KlineFrame
from pa_agent.records.schema import AnalysisRecord, RecordMeta
from pa_agent.util.mask_secret import mask_secret


def test_settings_payload_masks_all_secrets() -> None:
    settings = Settings()
    settings.provider.api_key = "sk-test-secret"
    settings.feishu.secret = "feishu-secret"
    settings.feishu.webhook_url = "https://open.feishu.cn/hook"
    settings.feishu.app_secret = "app-secret"
    settings.pushplus.token = "push-token"
    settings.tushare.token = "tushare-token"

    payload = settings_to_payload(settings)

    assert payload["provider"]["api_key"] == mask_secret("sk-test-secret")
    assert payload["feishu"]["secret"] == mask_secret("feishu-secret")
    assert payload["feishu"]["webhook_url"] == mask_secret("https://open.feishu.cn/hook")
    assert payload["feishu"]["app_secret"] == mask_secret("app-secret")
    assert payload["pushplus"]["token"] == mask_secret("push-token")
    assert payload["tushare"]["token"] == mask_secret("tushare-token")
    assert "api_key_encrypted" not in payload["provider"]


def test_settings_payload_masks_short_secret_values() -> None:
    settings = Settings()
    settings.provider.api_key = "abc"
    settings.feishu.secret = "xy"
    settings.pushplus.token = "z"

    payload = settings_to_payload(settings)

    assert payload["provider"]["api_key"] == "***"
    assert payload["feishu"]["secret"] == "***"
    assert payload["pushplus"]["token"] == "***"


def test_frame_payload_preserves_newest_first_contract() -> None:
    frame = KlineFrame(
        symbol="000001",
        timeframe="1h",
        bars=(
            KlineBar(1, 3000, 10, 13, 9, 12, 100, closed=True),
            KlineBar(2, 2000, 9, 11, 8, 10, 90, closed=True),
        ),
        indicators=IndicatorBundle(ema20=(11.5, 10.0), atr14=(1.5, 1.2)),
        snapshot_ts_local_ms=123456,
    )

    payload = frame_to_payload(frame)

    assert payload["order"] == "newest_first"
    assert payload["bar_count"] == 2
    assert [bar["seq"] for bar in payload["bars"]] == [1, 2]
    assert payload["bars"][0]["ts_open"] == 3000
    assert payload["indicators"]["ema20"] == [11.5, 10.0]


def test_frame_payload_converts_non_finite_numbers_to_null() -> None:
    frame = KlineFrame(
        symbol="000001",
        timeframe="1h",
        bars=(
            KlineBar(
                1,
                3000,
                math.nan,
                math.inf,
                9,
                12,
                math.inf,
                amount=math.nan,
                pct_chg=math.inf,
                closed=True,
            ),
        ),
        indicators=IndicatorBundle(ema20=(math.nan,), atr14=(math.inf,)),
        snapshot_ts_local_ms=123456,
    )

    payload = frame_to_payload(frame)

    assert payload["bars"][0]["open"] is None
    assert payload["bars"][0]["high"] is None
    assert payload["bars"][0]["volume"] is None
    assert payload["bars"][0]["amount"] is None
    assert payload["bars"][0]["pct_chg"] is None
    assert payload["indicators"]["ema20"] == [None]
    assert payload["indicators"]["atr14"] == [None]


def test_record_summary_does_not_expose_absolute_local_path(tmp_path) -> None:
    record = AnalysisRecord(
        meta=RecordMeta(
            timestamp_local_iso="2026-06-23T15:00:00+08:00",
            timestamp_local_ms=1,
            symbol="000001",
            timeframe="1h",
            bar_count=100,
            ai_provider={},
            decision_stance="balanced",
        ),
        kline_data=[],
        htf_text="",
        stage1_messages=[],
        stage1_response=None,
        stage1_diagnosis=None,
        stage2_messages=[],
        stage2_response=None,
        stage2_decision={"action": "wait", "direction": "none"},
        strategy_files_used=[],
        experience_loaded=[],
        exception=None,
        usage_total={},
    )

    payload = record_summary_to_payload(tmp_path / "secret" / "record.json", record)

    assert payload["id"] == "record"
    assert "path" not in payload
