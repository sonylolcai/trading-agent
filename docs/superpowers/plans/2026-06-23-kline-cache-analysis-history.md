# K-Line Cache And Analysis History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist fetched K-line bars between app launches and expose saved analysis records as a timestamped GUI history.

**Architecture:** Add a file-backed K-line cache under `cache/kline`, keyed by data source, symbol, and timeframe, with merge/dedupe logic isolated in `pa_agent/data/kline_cache.py`. Keep analysis records as the source of truth and add a small summary reader plus a read-only PyQt dialog for browsing recent analysis. `MainWindow` only wires cache load/save and opens the history dialog.

**Tech Stack:** Python 3, Pydantic settings, dataclasses, JSON files, pathlib, PyQt6, pytest.

---

## File Map

- Create `pa_agent/data/kline_cache.py`: JSON serialization, cache key sanitation, bar merge/dedupe, read/write helpers.
- Create `tests/unit/test_kline_cache.py`: unit tests for round trip, merge behavior, invalid metadata, and trimming.
- Modify `pa_agent/config/paths.py`: add `CACHE_DIR` and `KLINE_CACHE_DIR`.
- Modify `pa_agent/config/settings.py`: add cache/history settings to `GeneralSettings`.
- Create `pa_agent/records/analysis_summary.py`: compact timeline extraction from `records/pending/*.json`.
- Create `tests/unit/test_analysis_summary.py`: unit tests for successful, partial, corrupt, and newest-first summaries.
- Create `pa_agent/gui/analysis_history_dialog.py`: read-only table dialog for analysis summaries.
- Modify `pa_agent/gui/main_window.py`: load cached bars before refresh, save merged cache on refresh, add "分析历史" menu action, refresh history after record creation.
- Modify `pa_agent/gui/general_settings_dialog.py` only if exposing cache controls is necessary; first pass should rely on defaults and avoid extra UI.

---

### Task 1: K-Line Cache Core

**Files:**
- Create: `pa_agent/data/kline_cache.py`
- Modify: `pa_agent/config/paths.py`
- Modify: `pa_agent/config/settings.py`
- Test: `tests/unit/test_kline_cache.py`

- [ ] **Step 1: Write failing cache tests**

Create `tests/unit/test_kline_cache.py`:

```python
import json

from pa_agent.data.base import KlineBar
from pa_agent.data.kline_cache import KlineCacheStore, merge_bars_newest_first


def _bar(ts: float, close: float, *, seq: int = 1, closed: bool = True) -> KlineBar:
    return KlineBar(
        seq=seq,
        ts_open=ts,
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=100.0,
        amount=1000.0,
        pct_chg=None,
        closed=closed,
    )


def test_round_trip_reads_written_cache(tmp_path):
    store = KlineCacheStore(tmp_path)
    bars = [_bar(3000, 13, seq=1), _bar(2000, 12, seq=2), _bar(1000, 11, seq=3)]

    path = store.write("eastmoney", "000001", "1h", bars, max_bars=2000)
    loaded = store.read("eastmoney", "000001", "1h")

    assert path.exists()
    assert loaded is not None
    assert [b.ts_open for b in loaded.bars] == [3000, 2000, 1000]
    assert loaded.source == "eastmoney"
    assert loaded.symbol == "000001"
    assert loaded.timeframe == "1h"


def test_merge_prefers_fetched_bar_and_sorts_newest_first():
    cached = [_bar(2000, 20), _bar(1000, 10)]
    fetched = [_bar(3000, 31), _bar(2000, 22)]

    merged = merge_bars_newest_first(cached, fetched, max_bars=10)

    assert [(b.ts_open, b.close) for b in merged] == [
        (3000, 31),
        (2000, 22),
        (1000, 10),
    ]


def test_merge_trims_to_max_bars():
    merged = merge_bars_newest_first(
        cached=[_bar(1000, 10), _bar(0, 9)],
        fetched=[_bar(3000, 13), _bar(2000, 12)],
        max_bars=3,
    )

    assert [b.ts_open for b in merged] == [3000, 2000, 1000]


def test_read_ignores_mismatched_metadata(tmp_path):
    store = KlineCacheStore(tmp_path)
    path = store.path_for("eastmoney", "000001", "1h")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "mt5",
                "symbol": "000001",
                "timeframe": "1h",
                "saved_at": "2026-06-23T00:00:00+00:00",
                "bars": [],
            }
        ),
        encoding="utf-8",
    )

    assert store.read("eastmoney", "000001", "1h") is None


def test_read_ignores_invalid_json(tmp_path):
    store = KlineCacheStore(tmp_path)
    path = store.path_for("eastmoney", "000001", "1h")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    assert store.read("eastmoney", "000001", "1h") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/unit/test_kline_cache.py -q
```

Expected: FAIL because `pa_agent.data.kline_cache` does not exist.

- [ ] **Step 3: Add cache path constants**

Modify `pa_agent/config/paths.py`:

```python
CACHE_DIR: Path = PROJECT_ROOT / "cache"
KLINE_CACHE_DIR: Path = CACHE_DIR / "kline"
```

Place these next to the other runtime write directories.

- [ ] **Step 4: Add settings defaults**

Modify `GeneralSettings` in `pa_agent/config/settings.py`:

```python
    #: Persist fetched K-lines locally so charts can recover after restart.
    kline_cache_enabled: bool = True
    kline_cache_max_bars: int = Field(default=2000, ge=10, le=200000)
    #: Max rows shown in the analysis history dialog.
    analysis_history_max_rows: int = Field(default=200, ge=1, le=10000)
```

Place these after `analysis_bar_count` or near the other general UI/data-feed options.

- [ ] **Step 5: Implement cache module**

Create `pa_agent/data/kline_cache.py`:

```python
"""File-backed K-line cache for startup recovery and incremental refresh."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pa_agent.config.paths import KLINE_CACHE_DIR
from pa_agent.data.base import KlineBar, normalize_kline_bar

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_SAFE_PART_RE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class KlineCacheEntry:
    source: str
    symbol: str
    timeframe: str
    saved_at: str
    bars: list[KlineBar]


def _safe_part(value: str) -> str:
    text = (value or "").strip()
    safe = _SAFE_PART_RE.sub("_", text)
    safe = safe.strip("._-")
    return safe or "unknown"


def _bar_to_dict(bar: KlineBar) -> dict:
    return {
        "seq": int(bar.seq),
        "ts_open": float(bar.ts_open),
        "open": float(bar.open),
        "high": float(bar.high),
        "low": float(bar.low),
        "close": float(bar.close),
        "volume": float(bar.volume),
        "amount": float(getattr(bar, "amount", 0.0) or 0.0),
        "pct_chg": getattr(bar, "pct_chg", None),
        "closed": bool(getattr(bar, "closed", True)),
    }


def _bar_from_dict(raw: dict) -> KlineBar:
    return normalize_kline_bar(
        KlineBar(
            seq=int(raw.get("seq", 1)),
            ts_open=float(raw["ts_open"]),
            open=float(raw["open"]),
            high=float(raw["high"]),
            low=float(raw["low"]),
            close=float(raw["close"]),
            volume=float(raw.get("volume", 0.0) or 0.0),
            amount=float(raw.get("amount", 0.0) or 0.0),
            pct_chg=raw.get("pct_chg"),
            closed=bool(raw.get("closed", True)),
        )
    )


def merge_bars_newest_first(
    cached: Iterable[KlineBar],
    fetched: Iterable[KlineBar],
    *,
    max_bars: int,
) -> list[KlineBar]:
    """Merge two newest-first bar lists by ``ts_open``; fetched bars win."""
    by_ts: dict[float, KlineBar] = {}
    for bar in cached:
        normalized = normalize_kline_bar(bar)
        by_ts[float(normalized.ts_open)] = normalized
    for bar in fetched:
        normalized = normalize_kline_bar(bar)
        by_ts[float(normalized.ts_open)] = normalized

    merged = [by_ts[ts] for ts in sorted(by_ts.keys(), reverse=True)]
    if max_bars > 0:
        merged = merged[:max_bars]
    rebased: list[KlineBar] = []
    closed_seq = 0
    for bar in merged:
        if bar.closed:
            closed_seq += 1
            seq = closed_seq
        else:
            seq = 0
        rebased.append(
            KlineBar(
                seq=seq,
                ts_open=bar.ts_open,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                amount=getattr(bar, "amount", 0.0),
                pct_chg=getattr(bar, "pct_chg", None),
                closed=bar.closed,
            )
        )
    return rebased


class KlineCacheStore:
    def __init__(self, root: Path = KLINE_CACHE_DIR) -> None:
        self.root = root

    def path_for(self, source: str, symbol: str, timeframe: str) -> Path:
        filename = f"{_safe_part(symbol)}_{_safe_part(timeframe)}.json"
        return self.root / _safe_part(source) / filename

    def read(self, source: str, symbol: str, timeframe: str) -> KlineCacheEntry | None:
        path = self.path_for(source, symbol, timeframe)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if path.exists():
                logger.warning("Kline cache ignored: %s (%s)", path, exc)
            return None

        if raw.get("schema_version") != SCHEMA_VERSION:
            return None
        if raw.get("source") != source or raw.get("symbol") != symbol or raw.get("timeframe") != timeframe:
            return None

        try:
            bars = [_bar_from_dict(item) for item in raw.get("bars", [])]
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Kline cache invalid bars ignored: %s (%s)", path, exc)
            return None

        return KlineCacheEntry(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            saved_at=str(raw.get("saved_at", "")),
            bars=bars,
        )

    def write(
        self,
        source: str,
        symbol: str,
        timeframe: str,
        bars: Iterable[KlineBar],
        *,
        max_bars: int,
    ) -> Path:
        path = self.path_for(source, symbol, timeframe)
        trimmed = merge_bars_newest_first([], bars, max_bars=max_bars)
        data = {
            "schema_version": SCHEMA_VERSION,
            "source": source,
            "symbol": symbol,
            "timeframe": timeframe,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "bars": [_bar_to_dict(bar) for bar in trimmed],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
```

- [ ] **Step 6: Run cache tests**

Run:

```powershell
python -m pytest tests/unit/test_kline_cache.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit cache core**

```powershell
git add pa_agent/config/paths.py pa_agent/config/settings.py pa_agent/data/kline_cache.py tests/unit/test_kline_cache.py
git commit -m "feat: add kline file cache"
```

---

### Task 2: Analysis Summary Reader

**Files:**
- Create: `pa_agent/records/analysis_summary.py`
- Test: `tests/unit/test_analysis_summary.py`

- [ ] **Step 1: Write failing summary tests**

Create `tests/unit/test_analysis_summary.py`:

```python
import json

from pa_agent.records.analysis_summary import read_analysis_summaries


def _record(ts_ms: int, symbol: str = "000001", *, exception: dict | None = None) -> dict:
    return {
        "meta": {
            "timestamp_local_iso": "2026-06-23T10:00:00+08:00",
            "timestamp_local_ms": ts_ms,
            "symbol": symbol,
            "timeframe": "1h",
            "bar_count": 100,
            "ai_provider": {"model": "test"},
            "decision_stance": "balanced",
        },
        "kline_data": [],
        "htf_text": "",
        "stage1_messages": [],
        "stage1_response": {},
        "stage1_diagnosis": {
            "cycle_position": "trading_range",
            "current_bias": "neutral",
        },
        "stage2_messages": [],
        "stage2_response": {},
        "stage2_decision": {
            "decision": {
                "direction": "long",
                "order_type": "wait",
                "trade_confidence": 55,
                "estimated_win_rate_basis": "historical",
                "historical_sample_count": 47,
            }
        },
        "strategy_files_used": [],
        "experience_loaded": [],
        "exception": exception,
        "usage_total": {},
    }


def test_read_summaries_newest_first(tmp_path):
    (tmp_path / "old.json").write_text(json.dumps(_record(1000)), encoding="utf-8")
    (tmp_path / "new.json").write_text(json.dumps(_record(2000, symbol="000002")), encoding="utf-8")

    rows = read_analysis_summaries(tmp_path, limit=10)

    assert [row.symbol for row in rows] == ["000002", "000001"]
    assert rows[0].order_type == "wait"
    assert rows[0].cycle_position == "trading_range"
    assert rows[0].direction == "long"
    assert rows[0].trade_confidence == 55
    assert rows[0].win_rate_basis == "historical"
    assert rows[0].historical_sample_count == 47
    assert rows[0].status == "success"


def test_read_summaries_marks_partial_record(tmp_path):
    raw = _record(1000, exception={"stage": "stage2", "message": "bad json"})
    raw["_partial_reason"] = "stage2 validation failed"
    (tmp_path / "partial.json").write_text(json.dumps(raw), encoding="utf-8")

    rows = read_analysis_summaries(tmp_path, limit=10)

    assert len(rows) == 1
    assert rows[0].status == "partial"
    assert "stage2 validation failed" in rows[0].error_message


def test_read_summaries_skips_corrupt_json(tmp_path):
    (tmp_path / "broken.json").write_text("{bad-json", encoding="utf-8")
    (tmp_path / "ok.json").write_text(json.dumps(_record(1000)), encoding="utf-8")

    rows = read_analysis_summaries(tmp_path, limit=10)

    assert len(rows) == 1
    assert rows[0].symbol == "000001"


def test_read_summaries_respects_limit(tmp_path):
    for index in range(3):
        (tmp_path / f"{index}.json").write_text(json.dumps(_record(index)), encoding="utf-8")

    rows = read_analysis_summaries(tmp_path, limit=2)

    assert len(rows) == 2
    assert [row.timestamp_local_ms for row in rows] == [2, 1]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/unit/test_analysis_summary.py -q
```

Expected: FAIL because `pa_agent.records.analysis_summary` does not exist.

- [ ] **Step 3: Implement summary reader**

Create `pa_agent/records/analysis_summary.py`:

```python
"""Compact timeline summaries for saved analysis records."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pa_agent.config.paths import RECORDS_PENDING_DIR


@dataclass(frozen=True)
class AnalysisSummary:
    path: Path
    timestamp_local_iso: str
    timestamp_local_ms: int
    symbol: str
    timeframe: str
    status: str
    cycle_position: str
    direction: str
    order_type: str
    trade_confidence: int | None
    win_rate_basis: str
    historical_sample_count: int | None
    error_message: str


def _get_nested(raw: dict[str, Any], *keys: str, default: Any = "") -> Any:
    node: Any = raw
    for key in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
    return default if node is None else node


def _decision(raw: dict[str, Any]) -> dict[str, Any]:
    stage2 = raw.get("stage2_decision") or {}
    if not isinstance(stage2, dict):
        return {}
    decision = stage2.get("decision")
    if isinstance(decision, dict):
        return decision
    return stage2


def _status_and_error(raw: dict[str, Any]) -> tuple[str, str]:
    partial_reason = raw.get("_partial_reason")
    exception = raw.get("exception")
    if partial_reason:
        return "partial", str(partial_reason)
    if isinstance(exception, dict):
        message = exception.get("message") or exception.get("error") or exception.get("type")
        return "failed", str(message or exception)
    if exception:
        return "failed", str(exception)
    return "success", ""


def _summary_from_raw(path: Path, raw: dict[str, Any]) -> AnalysisSummary:
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    stage1 = raw.get("stage1_diagnosis") if isinstance(raw.get("stage1_diagnosis"), dict) else {}
    decision = _decision(raw)
    status, error_message = _status_and_error(raw)
    confidence = decision.get("trade_confidence")
    sample_count = decision.get("historical_sample_count")

    return AnalysisSummary(
        path=path,
        timestamp_local_iso=str(meta.get("timestamp_local_iso", "")),
        timestamp_local_ms=int(meta.get("timestamp_local_ms", 0) or 0),
        symbol=str(meta.get("symbol", "")),
        timeframe=str(meta.get("timeframe", "")),
        status=status,
        cycle_position=str(stage1.get("cycle_position") or stage1.get("market_phase") or ""),
        direction=str(decision.get("direction") or decision.get("trade_direction") or ""),
        order_type=str(decision.get("order_type") or decision.get("action") or ""),
        trade_confidence=int(confidence) if isinstance(confidence, (int, float)) else None,
        win_rate_basis=str(decision.get("estimated_win_rate_basis") or ""),
        historical_sample_count=int(sample_count) if isinstance(sample_count, (int, float)) else None,
        error_message=error_message,
    )


def read_analysis_summaries(
    directory: Path | None = None,
    *,
    limit: int = 200,
) -> list[AnalysisSummary]:
    root = directory or RECORDS_PENDING_DIR
    if not root.is_dir() or limit <= 0:
        return []

    rows: list[AnalysisSummary] = []
    for path in root.glob("*.json"):
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        rows.append(_summary_from_raw(path, raw))

    rows.sort(key=lambda row: (row.timestamp_local_ms, row.path.stat().st_mtime), reverse=True)
    return rows[:limit]
```

- [ ] **Step 4: Run summary tests**

Run:

```powershell
python -m pytest tests/unit/test_analysis_summary.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit summary reader**

```powershell
git add pa_agent/records/analysis_summary.py tests/unit/test_analysis_summary.py
git commit -m "feat: summarize saved analysis records"
```

---

### Task 3: GUI K-Line Cache Wiring

**Files:**
- Modify: `pa_agent/gui/main_window.py`
- Test: `tests/unit/test_kline_cache.py` from Task 1 plus manual GUI smoke.

- [ ] **Step 1: Add cache helper methods to `MainWindow`**

In `pa_agent/gui/main_window.py`, add these methods near `_start_refresh_loop` or near `_build_chart_frame_from_bars`:

```python
    def _kline_cache_enabled(self) -> bool:
        settings = getattr(self._ctx, "settings", None)
        if settings is None:
            return True
        return bool(getattr(settings.general, "kline_cache_enabled", True))

    def _kline_cache_max_bars(self) -> int:
        settings = getattr(self._ctx, "settings", None)
        if settings is None:
            return 2000
        return int(getattr(settings.general, "kline_cache_max_bars", 2000) or 2000)

    def _current_cache_identity(self) -> tuple[str, str, str]:
        return (
            self._current_data_source_kind(),
            self._symbol_combo.currentText().strip(),
            self._tf_combo.currentText(),
        )

    def _load_cached_kline_frame(self) -> None:
        if not self._kline_cache_enabled():
            return
        try:
            from pa_agent.data.kline_cache import KlineCacheStore

            source, symbol, timeframe = self._current_cache_identity()
            entry = KlineCacheStore().read(source, symbol, timeframe)
            if entry is None or not entry.bars:
                return
            self._last_frame_ready_bars = list(entry.bars)
            frame = self._build_chart_frame_from_bars(
                entry.bars,
                include_forming=False,
            )
            if frame is None:
                return
            self._chart_widget.set_frame_now(frame, fit_view=False)
            self._status_bar.showMessage(
                f"已加载本地缓存: {symbol} {timeframe}，等待数据源刷新"
            )
            self._refresh_incremental_label()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Load kline cache failed: %s", exc)

    def _save_kline_cache_from_bars(self, bars: Any) -> None:
        if not bars or not self._kline_cache_enabled():
            return
        try:
            from pa_agent.data.kline_cache import KlineCacheStore, merge_bars_newest_first

            source, symbol, timeframe = self._current_cache_identity()
            store = KlineCacheStore()
            cached = store.read(source, symbol, timeframe)
            cached_bars = cached.bars if cached is not None else []
            merged = merge_bars_newest_first(
                cached_bars,
                list(bars),
                max_bars=self._kline_cache_max_bars(),
            )
            store.write(
                source,
                symbol,
                timeframe,
                merged,
                max_bars=self._kline_cache_max_bars(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Save kline cache failed: %s", exc)
```

- [ ] **Step 2: Load cache before starting live refresh**

Modify `_start_refresh_loop` before creating `RefreshLoop`:

```python
        self._load_cached_kline_frame()
```

Place it after the data source connection check and before `from pa_agent.data.refresh_loop import RefreshLoop`.

- [ ] **Step 3: Save cache on every successful refresh payload**

Modify `_on_refresh_frame_ready` immediately after:

```python
            self._last_frame_ready_bars = list(bars)
```

Add:

```python
            self._save_kline_cache_from_bars(bars)
```

- [ ] **Step 4: Load cache after symbol/timeframe changes without auto-analysis**

In `_on_symbol_or_tf_changed`, after chart reset and after the new subscription state is settled, call:

```python
            self._load_cached_kline_frame()
```

If the function has an early-return path for invalid partial TradingView symbols, do not call cache there.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/unit/test_kline_cache.py -q
```

Expected: PASS.

- [ ] **Step 6: Manual GUI smoke**

Run the app normally, choose an A-share source, and click data fetch. Verify:

```text
cache/kline/eastmoney/000001_1h.json exists
Restart shows cached K-lines before live refresh completes
Live refresh still updates the chart
Switching symbol/timeframe does not auto-submit analysis
```

- [ ] **Step 7: Commit GUI cache wiring**

```powershell
git add pa_agent/gui/main_window.py
git commit -m "feat: restore chart from kline cache"
```

---

### Task 4: Analysis History Dialog

**Files:**
- Create: `pa_agent/gui/analysis_history_dialog.py`
- Modify: `pa_agent/gui/main_window.py`
- Test: `tests/unit/test_analysis_summary.py` plus manual GUI smoke.

- [ ] **Step 1: Implement read-only history dialog**

Create `pa_agent/gui/analysis_history_dialog.py`:

```python
"""Read-only dialog for browsing saved analysis summaries."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pa_agent.records.analysis_summary import AnalysisSummary


class AnalysisHistoryDialog(QDialog):
    HEADERS = [
        "时间",
        "标的",
        "周期",
        "状态",
        "周期位置",
        "方向",
        "动作",
        "信心",
        "胜率依据",
        "样本",
        "异常",
    ]

    def __init__(self, summaries: list[AnalysisSummary], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("分析历史")
        self.resize(1100, 520)

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(self.HEADERS), self)
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.set_summaries(summaries)

    def set_summaries(self, summaries: list[AnalysisSummary]) -> None:
        self._table.setRowCount(len(summaries))
        for row_index, summary in enumerate(summaries):
            values = [
                summary.timestamp_local_iso,
                summary.symbol,
                summary.timeframe,
                summary.status,
                summary.cycle_position,
                summary.direction,
                summary.order_type,
                "" if summary.trade_confidence is None else str(summary.trade_confidence),
                summary.win_rate_basis,
                "" if summary.historical_sample_count is None else str(summary.historical_sample_count),
                summary.error_message,
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row_index, col_index, item)
```

- [ ] **Step 2: Add menu action to main window**

In `pa_agent/gui/main_window.py` menu setup, after "生成回测统计":

```python
        _analysis_history_action = QAction("分析历史", self)
        _analysis_history_action.setToolTip("查看 records/pending 中保存的历史分析摘要")
        _analysis_history_action.triggered.connect(self._open_analysis_history_dialog)
        menu_bar.addAction(_analysis_history_action)
```

- [ ] **Step 3: Add dialog open method**

Add this method near other `_open_*_dialog` methods:

```python
    def _open_analysis_history_dialog(self) -> None:
        try:
            from pa_agent.gui.analysis_history_dialog import AnalysisHistoryDialog
            from pa_agent.records.analysis_summary import read_analysis_summaries

            settings = getattr(self._ctx, "settings", None)
            limit = 200
            if settings is not None:
                limit = int(getattr(settings.general, "analysis_history_max_rows", 200) or 200)
            summaries = read_analysis_summaries(limit=limit)
            dialog = AnalysisHistoryDialog(summaries, self)
            dialog.exec()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Open analysis history failed: %s", exc, exc_info=True)
            self._status_bar.showMessage(f"分析历史打开失败: {exc}")
```

- [ ] **Step 4: Refresh history naturally after analysis records are ready**

No persistent dialog refresh is needed in this pass because the dialog reads fresh summaries each time it opens. In `_on_record_ready`, after setting `self._last_analysis_record = record`, add only a status hint:

```python
        self._status_bar.showMessage("分析已保存，可在「分析历史」查看")
```

If this conflicts with more important error/status messaging later in `_on_record_ready`, skip this hint rather than overriding error status.

- [ ] **Step 5: Run summary tests**

Run:

```powershell
python -m pytest tests/unit/test_analysis_summary.py -q
```

Expected: PASS.

- [ ] **Step 6: Manual GUI smoke**

Run the app, click "分析历史", and verify:

```text
Dialog opens even with no records
Existing records show newest first
Partial/error records show status and error text
Close button closes the dialog
```

- [ ] **Step 7: Commit history GUI**

```powershell
git add pa_agent/gui/analysis_history_dialog.py pa_agent/gui/main_window.py
git commit -m "feat: show analysis history summaries"
```

---

### Task 5: Final Verification

**Files:**
- No new files unless fixing issues found during verification.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
python -m pytest tests/unit/test_kline_cache.py tests/unit/test_analysis_summary.py -q
```

Expected: PASS.

- [ ] **Step 2: Run relevant existing tests**

Run:

```powershell
python -m pytest tests/unit/test_settings_round_trip.py tests/unit/test_data_source_factory.py tests/unit/test_backtest_record_replay.py -q
```

Expected: PASS. If unrelated failures occur, record exact test names and reason in the final handoff.

- [ ] **Step 3: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors. CRLF warnings from Git on Windows are acceptable only if `git diff --check` exits 0.

- [ ] **Step 4: Manual end-to-end smoke**

Run the GUI and verify:

```text
First live fetch writes cache/kline/<source>/<symbol>_<timeframe>.json
Restart loads cached bars before live refresh
Live refresh merges newer bars without duplicating timestamps
Submitting analysis still saves records normally
Analysis History shows the saved record
Incremental analysis label still updates after cached or live bars are available
```

- [ ] **Step 5: Final commit**

If verification required small fixes, commit them:

```powershell
git add pa_agent tests docs
git commit -m "test: verify kline cache and analysis history"
```

Skip this commit if no files changed after the feature commits.

---

## Self-Review Notes

- Spec coverage: K-line disk cache is covered by Tasks 1 and 3; analysis timeline is covered by Tasks 2 and 4; settings defaults and bounded cache size are covered by Task 1; non-goals are preserved by keeping JSON files and avoiding replay/filter work.
- Marker scan: no task depends on an undefined module after the task that creates it; no unresolved marker tokens or open-ended "add tests later" steps remain.
- Type consistency: cache functions use `KlineBar` throughout; summary rows use `AnalysisSummary`; GUI imports those concrete types only after their tasks create them.
