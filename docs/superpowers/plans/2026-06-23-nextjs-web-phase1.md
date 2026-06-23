# Next.js Web Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first safe vertical slice of the Web migration: a FastAPI read-only API plus a Next.js terminal shell that can show masked settings, data-source metadata, a cached/current K-line snapshot, and analysis history.

**Architecture:** Python remains the domain/runtime layer. A new `pa_agent/api` package exposes existing settings, data-source, cache, snapshot, and record modules through REST. `apps/web` is a Next.js client that consumes those APIs through a small typed client and renders a dense trading-terminal shell without changing PyQt behavior.

**Tech Stack:** FastAPI, Pydantic v2, pytest, Next.js, React, TypeScript, TanStack Query, Zustand, lightweight-charts, Vitest.

---

## Scope

Implement only Phase 1 from `docs/superpowers/specs/2026-06-23-nextjs-web-migration-design.md`.

Included:

- `pa_agent/api` package.
- Read-only settings endpoint with secret masking.
- Data-source metadata endpoint.
- K-line cache metadata and snapshot endpoints.
- Analysis record summary endpoint.
- Local API app factory.
- Next.js app scaffold under `apps/web`.
- Terminal route shell and history route.
- TypeScript API client and chart data conversion helper.

Excluded:

- Live market SSE.
- Running AI analysis from Web.
- Settings writes.
- Electron packaging.
- Removing or modifying the PyQt GUI.
- Database migration.

## Files

Create:

- `pa_agent/api/__init__.py` - public API package marker.
- `pa_agent/api/dto.py` - serializable DTO builders for settings, bars, frames, records, and API errors.
- `pa_agent/api/context.py` - lightweight API context that loads settings without bootstrapping AI clients or opening MT5.
- `pa_agent/api/routes_settings.py` - read-only settings route.
- `pa_agent/api/routes_market.py` - data-source metadata, cache metadata, and snapshot routes.
- `pa_agent/api/routes_records.py` - history summary routes.
- `pa_agent/api/app.py` - FastAPI app factory and router wiring.
- `pa_agent/api/main.py` - `python -m pa_agent.api.main` entry point for local development.
- `tests/unit/test_api_dto.py` - DTO behavior and secret masking tests.
- `tests/unit/test_api_routes.py` - FastAPI TestClient route tests.
- `apps/web/package.json` - Web app scripts and dependency declarations.
- `apps/web/tsconfig.json` - TypeScript config.
- `apps/web/next.config.mjs` - Next.js config.
- `apps/web/vitest.config.ts` - unit-test config.
- `apps/web/app/layout.tsx` - root layout.
- `apps/web/app/page.tsx` - redirect to `/terminal`.
- `apps/web/app/terminal/page.tsx` - terminal workbench route.
- `apps/web/app/history/page.tsx` - history summary route.
- `apps/web/app/globals.css` - dense terminal styling.
- `apps/web/components/app-shell.tsx` - left navigation and page frame.
- `apps/web/components/status-chip.tsx` - compact state chip.
- `apps/web/features/terminal/terminal-workbench.tsx` - terminal layout and data fetching.
- `apps/web/features/history/history-page.tsx` - history table.
- `apps/web/features/chart/kline-chart-preview.tsx` - Phase 1 non-interactive chart preview rendered from real snapshot data.
- `apps/web/lib/api.ts` - typed API client.
- `apps/web/lib/chart.ts` - newest-first to oldest-first chart conversion.
- `apps/web/types/api.ts` - shared response types.
- `apps/web/__tests__/chart.test.ts` - chart conversion tests.

Modify:

- `pyproject.toml` - add FastAPI and uvicorn dependencies.
- `.gitignore` - ignore `apps/web/.next`, `apps/web/node_modules`, and coverage output if not already ignored.

Do not edit:

- `pa_agent/gui/*`
- `pa_agent/orchestrator/*`
- `pa_agent/ai/*`
- `pa_agent/data/*` except using existing public functions from API routes.

---

### Task 1: Python API DTOs And Secret Masking

**Files:**

- Create: `pa_agent/api/__init__.py`
- Create: `pa_agent/api/dto.py`
- Test: `tests/unit/test_api_dto.py`

- [ ] **Step 1: Write failing DTO tests**

Create `tests/unit/test_api_dto.py`:

```python
from __future__ import annotations

from pa_agent.api.dto import frame_to_payload, settings_to_payload
from pa_agent.config.settings import Settings
from pa_agent.data.base import IndicatorBundle, KlineBar, KlineFrame


def test_settings_payload_masks_all_secrets() -> None:
    settings = Settings()
    settings.provider.api_key = "sk-test-secret"
    settings.feishu.secret = "feishu-secret"
    settings.feishu.webhook_url = "https://open.feishu.cn/hook"
    settings.feishu.app_secret = "app-secret"
    settings.pushplus.token = "push-token"
    settings.tushare.token = "tushare-token"

    payload = settings_to_payload(settings)

    assert payload["provider"]["api_key"] == "***cret"
    assert payload["feishu"]["secret"] == "***cret"
    assert payload["feishu"]["webhook_url"] == "***hook"
    assert payload["feishu"]["app_secret"] == "***cret"
    assert payload["pushplus"]["token"] == "***oken"
    assert payload["tushare"]["token"] == "***oken"
    assert "api_key_encrypted" not in payload["provider"]


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
    assert [bar["seq"] for bar in payload["bars"]] == [1, 2]
    assert payload["bars"][0]["ts_open"] == 3000
    assert payload["indicators"]["ema20"] == [11.5, 10.0]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
pytest tests/unit/test_api_dto.py -q
```

Expected: fail because `pa_agent.api.dto` does not exist.

- [ ] **Step 3: Implement DTO helpers**

Create `pa_agent/api/__init__.py`:

```python
"""Local Web API for PA Agent."""
```

Create `pa_agent/api/dto.py`:

```python
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
    return _mask_mapping(settings.model_dump())


def bar_to_payload(bar: KlineBar) -> dict[str, Any]:
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
```

- [ ] **Step 4: Run DTO tests to verify GREEN**

Run:

```powershell
pytest tests/unit/test_api_dto.py -q
```

Expected: pass.

---

### Task 2: Python API Context And Routes

**Files:**

- Create: `pa_agent/api/context.py`
- Create: `pa_agent/api/routes_settings.py`
- Create: `pa_agent/api/routes_market.py`
- Create: `pa_agent/api/routes_records.py`
- Create: `pa_agent/api/app.py`
- Create: `pa_agent/api/main.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/test_api_routes.py`

- [ ] **Step 1: Write failing route tests**

Create `tests/unit/test_api_routes.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from pa_agent.api.app import create_app
from pa_agent.api.context import ApiContext
from pa_agent.config.settings import Settings
from pa_agent.data.base import KlineBar
from pa_agent.data.kline_cache import KlineCacheStore


def _context(tmp_path: Path) -> ApiContext:
    settings = Settings()
    settings.provider.api_key = "sk-test-secret"
    settings.general.last_data_source = "eastmoney"
    settings.general.last_symbol = "000001"
    settings.general.last_timeframe = "1h"
    settings.general.analysis_bar_count = 2
    return ApiContext(
        settings=settings,
        kline_cache=KlineCacheStore(tmp_path / "cache"),
        records_dir=tmp_path / "records",
    )


def _bar(seq: int, ts: float, close: float, *, closed: bool = True) -> KlineBar:
    return KlineBar(seq, ts, close - 1, close + 1, close - 2, close, 100, closed=closed)


def test_settings_route_masks_api_key(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["provider"]["api_key"] == "***cret"


def test_data_sources_route_lists_default_sources(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/data-sources")

    assert response.status_code == 200
    kinds = [item["kind"] for item in response.json()["items"]]
    assert kinds[:3] == ["eastmoney", "akshare", "tushare"]
    assert "mt5" in kinds


def test_market_snapshot_reads_cache_and_keeps_newest_first(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        [_bar(0, 4000, 14, closed=False), _bar(1, 3000, 13), _bar(2, 2000, 12)],
        max_bars=20,
    )
    client = TestClient(create_app(context))

    response = client.get("/api/market/snapshot?bars=2&include_forming=false")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "cache"
    assert payload["frame"]["order"] == "newest_first"
    assert [bar["seq"] for bar in payload["frame"]["bars"]] == [1, 2]
    assert [bar["ts_open"] for bar in payload["frame"]["bars"]] == [3000, 2000]


def test_market_snapshot_can_include_forming_bar_for_display(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        [_bar(0, 4000, 14, closed=False), _bar(1, 3000, 13), _bar(2, 2000, 12)],
        max_bars=20,
    )
    client = TestClient(create_app(context))

    response = client.get("/api/market/snapshot?bars=2&include_forming=true")

    assert response.status_code == 200
    payload = response.json()
    assert [bar["seq"] for bar in payload["frame"]["bars"]] == [0, 1, 2]


def test_records_route_returns_empty_list_when_no_records(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.get("/api/records")

    assert response.status_code == 200
    assert response.json() == {"items": []}
```

- [ ] **Step 2: Run route tests to verify RED**

Run:

```powershell
pytest tests/unit/test_api_routes.py -q
```

Expected: fail because route modules do not exist.

- [ ] **Step 3: Add FastAPI dependencies**

Modify `pyproject.toml` dependencies by adding:

```toml
    "fastapi>=0.115",
    "uvicorn>=0.30",
```

- [ ] **Step 4: Implement API context**

Create `pa_agent/api/context.py`:

```python
"""Runtime context for the local Web API."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pa_agent.config.paths import RECORDS_PENDING_DIR, SETTINGS_JSON_PATH
from pa_agent.config.settings import Settings, load_settings
from pa_agent.data.kline_cache import KlineCacheStore


@dataclass(slots=True)
class ApiContext:
    settings: Settings
    kline_cache: KlineCacheStore = field(default_factory=KlineCacheStore)
    records_dir: Path = RECORDS_PENDING_DIR

    @classmethod
    def load(cls) -> "ApiContext":
        return cls(settings=load_settings(SETTINGS_JSON_PATH))
```

- [ ] **Step 5: Implement settings route**

Create `pa_agent/api/routes_settings.py`:

```python
"""Settings routes for the local Web API."""
from __future__ import annotations

from fastapi import APIRouter, Request

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import settings_to_payload

router = APIRouter(prefix="/api", tags=["settings"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


@router.get("/settings")
def read_settings(request: Request) -> dict:
    return settings_to_payload(_ctx(request).settings)
```

- [ ] **Step 6: Implement market route**

Create `pa_agent/api/routes_market.py`:

```python
"""Market metadata and snapshot routes for the local Web API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import frame_to_payload
from pa_agent.data.factory import (
    DATA_SOURCE_CHOICES,
    data_source_label,
    default_symbol_for_kind,
    normalize_data_source_kind,
)
from pa_agent.data.snapshot import build_analysis_frame, build_live_frame

router = APIRouter(prefix="/api", tags=["market"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


@router.get("/data-sources")
def list_data_sources() -> dict[str, list[dict[str, str]]]:
    return {
        "items": [
            {
                "kind": kind,
                "label": data_source_label(kind),
                "default_symbol": default_symbol_for_kind(kind),
            }
            for kind, _label in DATA_SOURCE_CHOICES
        ]
    }


@router.get("/timeframes")
def list_timeframes(source: str | None = None) -> dict[str, list[str]]:
    _ = normalize_data_source_kind(source)
    return {"items": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]}


@router.get("/kline-cache")
def read_kline_cache(request: Request) -> dict:
    ctx = _ctx(request)
    general = ctx.settings.general
    kind = normalize_data_source_kind(general.last_data_source)
    entry = ctx.kline_cache.read(kind, general.last_symbol, general.last_timeframe)
    if entry is None:
        return {"available": False, "source": kind, "symbol": general.last_symbol, "timeframe": general.last_timeframe}
    return {
        "available": True,
        "source": entry.source,
        "symbol": entry.symbol,
        "timeframe": entry.timeframe,
        "saved_at": entry.saved_at,
        "bar_count": len(entry.bars),
    }


@router.get("/market/snapshot")
def read_market_snapshot(
    request: Request,
    bars: int = Query(default=100, ge=1, le=5000),
    include_forming: bool = False,
) -> dict:
    ctx = _ctx(request)
    general = ctx.settings.general
    kind = normalize_data_source_kind(general.last_data_source)
    entry = ctx.kline_cache.read(kind, general.last_symbol, general.last_timeframe)
    if entry is None:
        raise HTTPException(status_code=404, detail="No cached K-line data for current source/symbol/timeframe")

    raw_bars = list(entry.bars)
    if include_forming:
        frame = build_live_frame(raw_bars, bars, entry.symbol, entry.timeframe)
    else:
        frame = build_analysis_frame(raw_bars, bars, entry.symbol, entry.timeframe)
    if frame is None:
        raise HTTPException(status_code=422, detail="Not enough bars to build snapshot")
    return {"source": "cache", "cache_saved_at": entry.saved_at, "frame": frame_to_payload(frame)}
```

- [ ] **Step 7: Implement records route**

Create `pa_agent/api/routes_records.py`:

```python
"""Analysis record routes for the local Web API."""
from __future__ import annotations

from fastapi import APIRouter, Request

from pa_agent.api.context import ApiContext
from pa_agent.api.dto import record_summary_to_payload
from pa_agent.records.analysis_history import list_record_paths, load_record

router = APIRouter(prefix="/api", tags=["records"])


def _ctx(request: Request) -> ApiContext:
    return request.app.state.api_context


@router.get("/records")
def list_records(request: Request, limit: int = 200) -> dict[str, list[dict]]:
    ctx = _ctx(request)
    items: list[dict] = []
    for path in list_record_paths(ctx.records_dir)[:limit]:
        record = load_record(path)
        if record is None:
            continue
        items.append(record_summary_to_payload(path, record))
    return {"items": items}
```

- [ ] **Step 8: Implement app factory and runner**

Create `pa_agent/api/app.py`:

```python
"""FastAPI application factory for the local PA Agent Web API."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pa_agent.api.context import ApiContext
from pa_agent.api.routes_market import router as market_router
from pa_agent.api.routes_records import router as records_router
from pa_agent.api.routes_settings import router as settings_router


def create_app(context: ApiContext | None = None) -> FastAPI:
    app = FastAPI(title="PA Agent Local API")
    app.state.api_context = context or ApiContext.load()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(settings_router)
    app.include_router(market_router)
    app.include_router(records_router)
    return app


app = create_app()
```

Create `pa_agent/api/main.py`:

```python
"""Run the local PA Agent Web API."""
from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("pa_agent.api.app:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 9: Run route tests to verify GREEN**

Run:

```powershell
pytest tests/unit/test_api_dto.py tests/unit/test_api_routes.py -q
```

Expected: pass.

---

### Task 3: Next.js Shell, Typed Client, And Chart Conversion

**Files:**

- Create all files under `apps/web`.
- Modify: `.gitignore`
- Test: `apps/web/__tests__/chart.test.ts`

- [ ] **Step 1: Write failing chart conversion test**

Create `apps/web/__tests__/chart.test.ts`:

```typescript
import { describe, expect, it } from 'vitest';
import { toChartCandles } from '../lib/chart';
import type { KlineFramePayload } from '../types/api';

describe('toChartCandles', () => {
  it('converts backend newest-first bars to chart oldest-first bars', () => {
    const frame: KlineFramePayload = {
      symbol: '000001',
      timeframe: '1h',
      order: 'newest_first',
      snapshot_ts_local_ms: 123,
      indicators: { ema20: [12, 10], atr14: [1.5, 1.2] },
      bars: [
        { seq: 1, ts_open: 3000, open: 10, high: 13, low: 9, close: 12, volume: 100, amount: 0, pct_chg: null, closed: true },
        { seq: 2, ts_open: 2000, open: 9, high: 11, low: 8, close: 10, volume: 90, amount: 0, pct_chg: null, closed: true },
      ],
    };

    expect(toChartCandles(frame).map((bar) => bar.seq)).toEqual([2, 1]);
    expect(toChartCandles(frame).map((bar) => bar.time)).toEqual([2, 3]);
  });
});
```

- [ ] **Step 2: Create Web project files**

Create `apps/web/package.json`:

```json
{
  "name": "pa-agent-web",
  "private": true,
  "scripts": {
    "dev": "next dev -H 127.0.0.1 -p 3000",
    "build": "next build",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.62.0",
    "lightweight-charts": "^5.0.0",
    "lucide-react": "^0.468.0",
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.7.0",
    "vitest": "^2.1.0"
  }
}
```

Create minimal Next.js config, TypeScript config, root layout, terminal page, history page, API client, and chart helper.

The chart helper must be:

```typescript
import type { KlineFramePayload } from '../types/api';

export type ChartCandle = {
  time: number;
  seq: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: boolean;
};

export function toChartCandles(frame: KlineFramePayload): ChartCandle[] {
  const bars = frame.order === 'newest_first' ? [...frame.bars].reverse() : [...frame.bars];
  return bars.map((bar) => ({
    time: Math.floor(bar.ts_open / 1000),
    seq: bar.seq,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
    closed: bar.closed,
  }));
}
```

- [ ] **Step 3: Run Web tests to verify GREEN**

Run:

```powershell
cd apps/web
npm install
npm test
npm run typecheck
```

Expected: chart conversion test passes and TypeScript typecheck passes.

---

### Task 4: Integration Verification And Commit

**Files:**

- Modify only files created or touched by Tasks 1-3.

- [ ] **Step 1: Run focused Python tests**

Run:

```powershell
pytest tests/unit/test_api_dto.py tests/unit/test_api_routes.py tests/unit/test_kline_cache.py tests/unit/test_build_analysis_frame.py -q
```

Expected: pass.

- [ ] **Step 2: Run Web tests**

Run:

```powershell
cd apps/web
npm test
npm run typecheck
```

Expected: pass.

- [ ] **Step 3: Check git status**

Run:

```powershell
git status --short
```

Expected: only Phase 1 files and the pre-existing untracked `运行智能体.bat`.

- [ ] **Step 4: Commit**

Run:

```powershell
git add pyproject.toml .gitignore pa_agent/api tests/unit/test_api_dto.py tests/unit/test_api_routes.py apps/web
git commit -m "feat: add nextjs web phase1 shell"
```

Expected: commit succeeds.

---

## Self-Review

Spec coverage:

- FastAPI app under `pa_agent/api`: Tasks 1-2.
- Next.js app under `apps/web`: Task 3.
- Settings read API: Task 2.
- Data-source metadata API: Task 2.
- Cached snapshot API: Task 2.
- Terminal layout shell: Task 3.
- Read-only chart render from snapshot: Task 3 starts with a real data preview and conversion helper; full `lightweight-charts` rendering is Phase 2.
- History summary list: Tasks 2-3.

Known intentional gap:

- Main K-line chart uses a Phase 1 snapshot preview, not full chart parity. Full `lightweight-charts` overlays, EMA, volume panes, and sequence-label overlays belong to Phase 2.
