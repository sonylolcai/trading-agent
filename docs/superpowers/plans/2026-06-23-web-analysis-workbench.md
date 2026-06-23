# Web Analysis Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Web app useful for PA Agent's core workflow: submit a cached closed-bar snapshot for two-stage analysis, stream and inspect Stage 1/Stage 2 output, show the final decision, and rebuild/view basic backtest setup statistics.

**Architecture:** Python remains the owner of analysis, records, cancellation, and backtest statistics. FastAPI adds a thin task manager and SSE event adapter around `TwoStageOrchestrator.submit()`. Next.js consumes the task API, shows the analysis stream and decision panel, and adds a small Backtest page for setup-stat feedback.

**Tech Stack:** FastAPI, Pydantic-compatible dict DTOs, Python threads/queues, pytest, Next.js App Router, React, TypeScript, Vitest.

---

## Scope

Included:

- `POST /api/analysis` starts an analysis task from the current cached closed-only frame.
- `GET /api/analysis/{analysis_id}` returns task status and final summary.
- `DELETE /api/analysis/{analysis_id}` requests cancellation.
- `GET /api/analysis/{analysis_id}/events` streams Stage 1/Stage 2 events as SSE.
- Terminal page shows Stage Stream, Decision, Stats Basis, Snapshot, and Debug panels.
- `POST /api/backtest/rebuild-setup-stats` rebuilds setup statistics from saved records.
- `GET /api/backtest/setup-stats` returns compact rows from `config/setup_stats.json`.
- Backtest page shows rebuild summary and setup-stat table.

Excluded:

- Full K-line parity.
- Live market stream.
- Web settings writes.
- Follow-up chat and record detail pages.
- Electron packaging.

## File Ownership

Hermes/backend owns:

- Create: `pa_agent/api/events.py`
- Create: `pa_agent/api/analysis_service.py`
- Create: `pa_agent/api/routes_analysis.py`
- Create: `pa_agent/api/routes_backtest.py`
- Modify: `pa_agent/api/context.py`
- Modify: `pa_agent/api/dto.py`
- Modify: `pa_agent/api/app.py`
- Test: `tests/unit/test_api_analysis.py`
- Test: `tests/unit/test_api_backtest_routes.py`

Anti/frontend owns:

- Modify: `apps/web/types/api.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/components/app-shell.tsx`
- Modify: `apps/web/features/terminal/terminal-workbench.tsx`
- Create: `apps/web/features/analysis/analysis-event-stream.ts`
- Create: `apps/web/features/analysis/decision-summary.tsx`
- Create: `apps/web/features/backtest/backtest-page.tsx`
- Create: `apps/web/app/backtest/page.tsx`
- Test: `apps/web/__tests__/analysis-events.test.ts`

The controller owns integration review, final tests, and commits.

---

### Task 1: Backend Analysis Task API

**Files:**

- Create: `pa_agent/api/events.py`
- Create: `pa_agent/api/analysis_service.py`
- Create: `pa_agent/api/routes_analysis.py`
- Modify: `pa_agent/api/context.py`
- Modify: `pa_agent/api/dto.py`
- Modify: `pa_agent/api/app.py`
- Test: `tests/unit/test_api_analysis.py`

- [ ] **Step 1: Write failing tests**

Create tests that inject a fake analysis runner into `ApiContext`. The fake runner receives a closed-only `KlineFrame`, emits:

```python
emit({"type": "stage_started", "stage": "stage1"})
emit({"type": "content_delta", "stage": "stage1", "text": "diagnosis"})
emit({"type": "stage_started", "stage": "stage2"})
emit({"type": "content_delta", "stage": "stage2", "text": "decision"})
```

and returns a minimal `AnalysisRecord`.

Assertions:

- `POST /api/analysis` returns `202`, `analysis_id`, `status: "running"`, and frame metadata.
- The fake runner receives no forming bar; `frame.bars[0].seq == 1`.
- `GET /api/analysis/{id}` eventually returns `status: "succeeded"`.
- `GET /api/analysis/{id}/events` returns `text/event-stream` data containing `stage_started`, `content_delta`, and `task_finished`.
- `DELETE /api/analysis/{id}` sets the task cancel token and returns `status: "cancelling"` when task is still running.

- [ ] **Step 2: Implement event and task service**

Implement `AnalysisTaskStore` with:

- `start(frame, runner) -> AnalysisTask`
- `get(analysis_id)`
- `cancel(analysis_id)`
- per-task `Queue[dict]`
- final status: `queued | running | succeeded | failed | cancelled`
- SSE generator that yields `event: message\ndata: <json>\n\n` until terminal event.

- [ ] **Step 3: Implement production runner**

The default runner:

- lazily calls `AppContext.bootstrap()` inside the background thread;
- builds `TwoStageOrchestrator`;
- wires `on_event`, `on_stage1_reasoning`, `on_stage1_content`, `on_stage2_reasoning`, `on_stage2_content`, `on_stage_prompt`, and `on_stage2_files` into normalized event dictionaries;
- returns the final `AnalysisRecord`.

- [ ] **Step 4: Implement routes**

`POST /api/analysis`:

- reads current settings source/symbol/timeframe;
- loads cache through `KlineCacheStore`;
- builds closed-only frame using `build_analysis_frame`;
- starts an analysis task;
- returns metadata.

`GET /api/analysis/{analysis_id}`:

- returns current task status, event count, frame metadata, and final record summary/decision if available.

`DELETE /api/analysis/{analysis_id}`:

- calls `CancelToken.set()`.

`GET /api/analysis/{analysis_id}/events`:

- streams SSE from the task queue.

- [ ] **Step 5: Verify**

Run:

```powershell
pytest tests/unit/test_api_analysis.py tests/unit/test_api_routes.py -q
```

Expected: pass.

---

### Task 2: Backend Backtest Stats API

**Files:**

- Create: `pa_agent/api/routes_backtest.py`
- Modify: `pa_agent/api/dto.py`
- Modify: `pa_agent/api/app.py`
- Test: `tests/unit/test_api_backtest_routes.py`

- [ ] **Step 1: Write failing tests**

Tests should cover:

- `POST /api/backtest/rebuild-setup-stats` calls a fake rebuild function and returns `records_scanned`, `trade_signals`, `completed_trades`, `setup_buckets`, and `output_path`.
- `GET /api/backtest/setup-stats` reads a temporary setup stats JSON such as:

```json
{
  "stock|1h|normal_channel|bullish|breakout|l1|balanced": [1.2, -1.0, 0.8]
}
```

and returns one row with `sample_count: 3`, `wins: 2`, `losses: 1`, `win_rate_pct: 66.666...`, `expectancy_r: 0.333...`.

- [ ] **Step 2: Implement routes**

`POST /api/backtest/rebuild-setup-stats` calls `rebuild_setup_stats_from_records(records_dir=ctx.records_dir, output_path=ctx.setup_stats_path)`.

`GET /api/backtest/setup-stats` loads `SetupStatsLedger.load_json(ctx.setup_stats_path)` and returns sorted rows by descending sample count.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest tests/unit/test_api_backtest_routes.py tests/unit/test_backtest_record_replay.py -q
```

Expected: pass.

---

### Task 3: Frontend Analysis Workbench

**Files:**

- Modify: `apps/web/types/api.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/features/terminal/terminal-workbench.tsx`
- Create: `apps/web/features/analysis/analysis-event-stream.ts`
- Create: `apps/web/features/analysis/decision-summary.tsx`
- Test: `apps/web/__tests__/analysis-events.test.ts`

- [ ] **Step 1: Write failing TypeScript tests**

Create tests for `parseAnalysisEvent()`:

- parses `event: message\ndata: {"type":"content_delta","stage":"stage1","text":"abc"}\n\n`;
- ignores blank chunks;
- returns `null` for malformed JSON.

- [ ] **Step 2: Extend API client**

Add:

- `api.startAnalysis()`
- `api.analysisStatus(id)`
- `api.cancelAnalysis(id)`
- `analysisEventsUrl(id)`

- [ ] **Step 3: Update terminal workbench**

Add:

- submit analysis button;
- cancel button when running;
- stream panes for Stage 1 and Stage 2 reasoning/content;
- decision summary using final `stage2_decision`;
- stats basis showing `estimated_win_rate_basis`, `historical_sample_count`, `historical_win_rate_for_this_setup`, and `historical_expectancy_r`;
- errors for insufficient data, provider failure, validation failure, and cancellation.

- [ ] **Step 4: Verify**

Run:

```powershell
cd apps/web
npm test
npm run typecheck
```

Expected: pass.

---

### Task 4: Frontend Backtest Page

**Files:**

- Modify: `apps/web/types/api.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/components/app-shell.tsx`
- Create: `apps/web/features/backtest/backtest-page.tsx`
- Create: `apps/web/app/backtest/page.tsx`

- [ ] **Step 1: Implement route and nav**

Add `/backtest` to the left rail.

- [ ] **Step 2: Implement page**

The page should:

- load setup stats on open;
- show a rebuild button;
- display rebuild summary;
- display setup rows in a compact table;
- show explicit offline/error state if the API is unavailable.

- [ ] **Step 3: Verify**

Run:

```powershell
cd apps/web
npm run typecheck
npm run build
```

Expected: pass.

---

## Integration Verification

Run:

```powershell
pytest tests/unit/test_api_dto.py tests/unit/test_api_routes.py tests/unit/test_api_analysis.py tests/unit/test_api_backtest_routes.py tests/unit/test_kline_cache.py tests/unit/test_build_analysis_frame.py -q
```

Run:

```powershell
cd apps/web
npm test
npm run typecheck
npm run build
```

Expected:

- Python tests pass.
- Web tests pass.
- Next build succeeds.
- `git status --short` shows only intended files plus the pre-existing untracked `运行智能体.bat`.

## Self-Review

This plan implements the revised Phase 2 and the first slice of Phase 4 from the migration spec. It intentionally keeps the chart as a minimal snapshot preview, defers live market streaming, and does not implement settings writes, follow-up chat, Electron, or full record detail.
