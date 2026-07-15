from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable

from fastapi.testclient import TestClient

from pa_agent.api.app import create_app
from pa_agent.api.context import ApiContext
from pa_agent.config.settings import Settings
from pa_agent.data.base import IndicatorBundle, KlineBar, KlineFrame
from pa_agent.data.kline_cache import KlineCacheStore
from pa_agent.records.schema import AnalysisRecord, RecordMeta
from pa_agent.util.threading import CancelToken


def _bar(seq: int, ts: float, close: float, *, closed: bool = True) -> KlineBar:
    return KlineBar(seq, ts, close - 1, close + 1, close - 2, close, 100, closed=closed)


def _recent_hourly_bars() -> list[KlineBar]:
    now_ms = int(time.time() * 1000)
    hour_ms = 60 * 60 * 1000
    return [
        _bar(0, now_ms, 14, closed=False),
        _bar(1, now_ms - hour_ms, 13),
        _bar(2, now_ms - 2 * hour_ms, 12),
        _bar(3, now_ms - 3 * hour_ms, 11),
    ]


def _record(frame: KlineFrame) -> AnalysisRecord:
    return AnalysisRecord(
        meta=RecordMeta(
            timestamp_local_iso="2026-06-23T12:00:00.000",
            timestamp_local_ms=1_781_000_000_000,
            symbol=frame.symbol,
            timeframe=frame.timeframe,
            bar_count=len(frame.bars),
            ai_provider={},
            decision_stance="balanced",
        ),
        kline_data=[
            {
                "seq": bar.seq,
                "ts_open": bar.ts_open,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "closed": bar.closed,
            }
            for bar in frame.bars
        ],
        htf_text="",
        stage1_messages=[],
        stage1_response=None,
        stage1_diagnosis={"cycle_position": "normal_channel"},
        stage2_messages=[],
        stage2_response=None,
        stage2_decision={
            "decision": {
                "order_type": "market",
                "direction": "long",
                "entry_price": 13,
                "take_profit_price": 15,
                "stop_loss_price": 12,
            },
            "estimated_win_rate_basis": "historical",
            "historical_sample_count": 3,
            "historical_win_rate_for_this_setup": 66.7,
            "historical_expectancy_r": 0.33,
        },
        strategy_files_used=[],
        experience_loaded=[],
        exception=None,
        usage_total={"total_tokens": 42, "cached_prompt_tokens": 7},
    )


class FakeAnalysisRunner:
    def __init__(self) -> None:
        self.frames: list[KlineFrame] = []
        self.cancel_tokens: list[CancelToken] = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.block = False

    def __call__(
        self,
        frame: KlineFrame,
        cancel_token: CancelToken,
        emit: Callable[[dict], None],
    ) -> AnalysisRecord:
        self.frames.append(frame)
        self.cancel_tokens.append(cancel_token)
        self.started.set()
        emit({"type": "stage_started", "stage": "stage1"})
        emit({"type": "content_started", "stage": "stage1", "format": "json"})
        emit({"type": "content_delta", "stage": "stage1", "text": "diagnosis"})
        emit({"type": "content_finished", "stage": "stage1", "format": "json", "text": "diagnosis"})
        if self.block:
            self.release.wait(timeout=2)
            if cancel_token.is_set():
                emit({"type": "cancelled"})
                return _record(frame)
        emit({"type": "stage_started", "stage": "stage2"})
        emit({"type": "content_started", "stage": "stage2", "format": "json"})
        emit({"type": "content_delta", "stage": "stage2", "text": "decision"})
        emit({"type": "content_finished", "stage": "stage2", "format": "json", "text": "decision"})
        return _record(frame)


class FakeKlineSource:
    def __init__(self, bars: list[KlineBar]) -> None:
        self.bars = bars
        self.connected = False
        self.disconnected = False
        self.subscriptions: list[tuple[str, str]] = []
        self.latest_requests: list[int] = []

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.disconnected = True

    def list_symbols(self) -> list[str]:
        return ["000001"]

    def supported_timeframes(self) -> list[str]:
        return ["1h"]

    def subscribe(self, symbol: str, timeframe: str) -> None:
        self.subscriptions.append((symbol, timeframe))

    def unsubscribe(self) -> None:
        pass

    def latest_snapshot(self, n: int) -> list[KlineBar]:
        self.latest_requests.append(n)
        return self.bars


def _context(
    tmp_path: Path,
    runner: FakeAnalysisRunner,
    *,
    seed_cache: bool = True,
) -> ApiContext:
    settings = Settings()
    settings.general.last_data_source = "eastmoney"
    settings.general.last_symbol = "000001"
    settings.general.last_timeframe = "1h"
    settings.general.analysis_bar_count = 2
    context = ApiContext(
        settings=settings,
        kline_cache=KlineCacheStore(tmp_path / "cache"),
        records_dir=tmp_path / "records",
        analysis_runner=runner,
    )
    if seed_cache:
        context.kline_cache.write(
            "eastmoney",
            "000001",
            "1h",
            _recent_hourly_bars(),
            max_bars=20,
        )
    return context


def _wait_for_status(client: TestClient, analysis_id: str, status: str) -> dict:
    for _ in range(50):
        payload = client.get(f"/api/analysis/{analysis_id}").json()
        if payload["status"] == status:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"analysis {analysis_id} did not reach {status}")


def test_analysis_task_uses_cached_closed_only_frame_and_streams_events(tmp_path: Path) -> None:
    runner = FakeAnalysisRunner()
    client = TestClient(create_app(_context(tmp_path, runner)))

    created = client.post("/api/analysis")

    assert created.status_code == 202
    created_payload = created.json()
    analysis_id = created_payload["analysis_id"]
    assert created_payload["status"] == "running"
    assert created_payload["frame"]["symbol"] == "000001"
    assert [bar["seq"] for bar in created_payload["frame"]["bars"]] == [1, 2]

    status_payload = _wait_for_status(client, analysis_id, "succeeded")
    assert status_payload["event_count"] >= 5
    assert status_payload["record"]["symbol"] == "000001"
    assert status_payload["record"]["stage2_decision"]["decision"]["order_type"] == "market"
    assert status_payload["record"]["analysis_report"]["decision"]["order_type"] == "market"
    assert status_payload["analysis_report"]["decision"]["order_type"] == "market"
    assert status_payload["record"]["usage_total"]["total_tokens"] == 42
    assert status_payload["stage2_decision"]["decision"]["order_type"] == "market"
    assert status_payload["usage_total"]["total_tokens"] == 42
    assert status_payload["record_summary"]["symbol"] == "000001"

    assert len(runner.frames) == 1
    assert [bar.seq for bar in runner.frames[0].bars] == [1, 2]
    assert all(bar.closed for bar in runner.frames[0].bars)

    events_response = client.get(f"/api/analysis/{analysis_id}/events")
    assert events_response.status_code == 200
    assert events_response.headers["content-type"].startswith("text/event-stream")
    body = events_response.text
    assert "event: message" in body
    assert '"type":"stage_started"' in body
    assert '"type":"content_started"' in body
    assert '"type":"content_delta"' in body
    assert '"type":"content_finished"' in body
    assert '"type":"task_finished"' in body
    parsed_events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert [event["type"] for event in parsed_events][-1] == "task_finished"


def test_empty_analysis_record_captures_risk_profile_and_threshold() -> None:
    from pa_agent.orchestrator.two_stage import _build_empty_record

    settings = Settings()
    settings.general.decision_stance = "aggressive"
    settings.general.decision_confidence_threshold = 30
    frame = KlineFrame(
        symbol="000001",
        timeframe="1h",
        bars=tuple(_recent_hourly_bars()[1:3]),
        indicators=IndicatorBundle(ema20=(12.0, 11.0), atr14=(1.0, 1.0)),
        snapshot_ts_local_ms=1,
    )

    record = _build_empty_record(frame, settings)

    assert record.meta.decision_stance == "aggressive"
    assert record.meta.decision_confidence_threshold == 30


def test_analysis_task_fetches_kline_data_when_cache_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = FakeAnalysisRunner()
    source = FakeKlineSource(_recent_hourly_bars())
    monkeypatch.setattr("pa_agent.data.factory.create_data_source", lambda kind: source)
    context = _context(tmp_path, runner, seed_cache=False)
    client = TestClient(create_app(context))

    created = client.post("/api/analysis")

    assert created.status_code == 202
    assert source.connected is True
    assert source.disconnected is True
    assert source.subscriptions == [("000001", "1h")]
    assert source.latest_requests and source.latest_requests[0] >= 2
    assert context.kline_cache.read("eastmoney", "000001", "1h") is not None
    assert [bar["seq"] for bar in created.json()["frame"]["bars"]] == [1, 2]


def test_analysis_task_refetches_when_cached_bars_are_insufficient(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = FakeAnalysisRunner()
    source = FakeKlineSource(_recent_hourly_bars())
    monkeypatch.setattr("pa_agent.data.factory.create_data_source", lambda kind: source)
    context = _context(tmp_path, runner, seed_cache=False)
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        [_bar(1, int(time.time() * 1000) - 60 * 60 * 1000, 13)],
        max_bars=20,
    )
    client = TestClient(create_app(context))

    created = client.post("/api/analysis")

    assert created.status_code == 202
    assert source.latest_requests and source.latest_requests[0] >= 2
    assert [bar["seq"] for bar in created.json()["frame"]["bars"]] == [1, 2]


def test_analysis_task_can_be_cancelled(tmp_path: Path) -> None:
    runner = FakeAnalysisRunner()
    runner.block = True
    client = TestClient(create_app(_context(tmp_path, runner)))

    created = client.post("/api/analysis")
    analysis_id = created.json()["analysis_id"]
    assert runner.started.wait(timeout=1)

    cancelled = client.delete(f"/api/analysis/{analysis_id}")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelling"
    assert runner.cancel_tokens[0].is_set()
    runner.release.set()
    _wait_for_status(client, analysis_id, "cancelled")


def test_analysis_status_exposes_record_exception_message(tmp_path: Path) -> None:
    class FailingRunner(FakeAnalysisRunner):
        def __call__(
            self,
            frame: KlineFrame,
            cancel_token: CancelToken,
            emit: Callable[[dict], None],
        ) -> AnalysisRecord:
            self.frames.append(frame)
            self.cancel_tokens.append(cancel_token)
            self.started.set()
            emit({"type": "stage_started", "stage": "stage1"})
            return _record(frame).model_copy(
                update={
                    "exception": {
                        "type": "validation_error",
                        "stage": "stage2",
                        "message": "stage2 schema failed",
                    }
                }
            )

    runner = FailingRunner()
    client = TestClient(create_app(_context(tmp_path, runner)))

    created = client.post("/api/analysis")
    analysis_id = created.json()["analysis_id"]
    failed_payload = _wait_for_status(client, analysis_id, "failed")

    assert failed_payload["error"] == "stage2 schema failed"
