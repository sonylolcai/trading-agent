# Next.js Web Migration Design

## Problem

PA Agent is currently a PyQt6 desktop application. The business logic is valuable and already reasonably separated from the GUI: market data sources, K-line snapshots, two-stage AI orchestration, records, backtesting, setup statistics, and local JSON persistence all live outside most GUI widgets. The PyQt layer now carries too much application coordination: refresh loops, worker lifecycles, streaming display, chart rendering, settings dialogs, history dialogs, demo replay, and status handling.

The goal is to keep the trading and analysis behavior intact while replacing the GUI with a Web interface that can later be packaged as an Electron desktop app. After the Phase 1 vertical slice, the migration priority is the analysis workflow, backtest feedback, and record review. Full chart parity and live market streaming are deferred because PA Agent's core value is AI price-action analysis, not becoming a full trading chart terminal.

## Decision

Use a staged architecture:

```text
Next.js + React front end
Python FastAPI local back end
Optional Electron shell after the Web version is stable
```

Do not move trading, AI, data source, record, cache, or backtest logic into Node.js. Next.js should replace the presentation layer, not the domain layer. Python remains the owner of market data, snapshots, analysis orchestration, records, settings, caching, backtesting, and notifications.

Electron should be deferred. It should eventually start and supervise the Python API process, open the local Web UI, manage tray/window behavior, and handle packaging. It should not contain trading or AI logic.

## Non-Goals

- Do not rewrite `pa_agent/data`, `pa_agent/ai`, `pa_agent/orchestrator`, `pa_agent/backtest`, or `pa_agent/records` in TypeScript.
- Do not remove the PyQt GUI during the first migration phase.
- Do not introduce a database in the first Web version.
- Do not build a marketing landing page.
- Do not start with Electron packaging before the local Web app is usable.
- Do not weaken the closed-bar K-line semantics used by the current AI pipeline.
- Do not treat PyQt chart parity as a blocker for Web analysis workflows.
- Do not implement live market streaming before Web analysis and backtest flows are usable.

## Current Functional Surface

The Web version must preserve these user-facing capabilities:

- Market source selection: East Money, AkShare, Tushare, TradingView, MT5.
- Symbol, exchange, timeframe, and refresh controls.
- Cached K-line recovery, minimal K-line snapshot preview, and closed-bar analysis snapshots.
- Manual analysis, automatic incremental analysis labeling, forced incremental analysis, wait-for-close, and continuous tracking.
- Stage 1 and Stage 2 streaming output with reasoning/content separation.
- Decision display: order type, direction, entry, take profit, stop loss, confidence, win-rate basis, sample count, and reasoning.
- Minimal K-line preview for orientation. EMA20, sequence labels, support/resistance, entry/take-profit/stop-loss overlays, and full interactive chart parity are optional later work.
- Follow-up chat after an analysis record.
- Settings for AI provider, API key, reasoning effort, analysis behavior, chart display, notifications, and decision-flow playback.
- Analysis history, record detail, demo replay, prompt/debug visibility, and backtest/setup-statistics generation.
- Token and cache-hit reporting.
- API-key missing state and provider/validation error diagnostics.

## Target Information Architecture

The Web app should be an operational terminal, not a landing page.

Routes:

```text
/terminal   Main trading-analysis workbench
/history    Analysis history, filtering, record detail, replay entry
/backtest   Setup statistics and backtest sample quality
/settings   AI, analysis, chart, notification, and decision-flow settings
/debug      Raw prompts, responses, validation errors, injected files, exports
```

Main workbench layout:

- Left rail: Terminal, History, Backtest, Settings, Debug.
- Top control bar: current data source, symbol, timeframe, refresh cached snapshot, submit analysis, cancel analysis.
- Main area: analysis stream and decision panel first; K-line snapshot preview is secondary.
- Bottom status bar: connection state, latest refresh age, current stage, API-key warnings, demo mode, token/cache summary.

Analysis workbench tabs:

```text
Stage Stream | Decision | Stats Basis | Snapshot | Debug
```

The active tab should follow workflow state:

- Analysis running: Stage Stream.
- Order opportunity: Decision.
- Validation/provider failure: Debug.
- Demo replay: current replay stage.

## Visual Direction

The UI should be compact, dense, and easy to scan repeatedly. It should feel like a trading-analysis terminal:

- restrained dark or neutral theme;
- clear status colors;
- compact inputs and tables;
- monospace numeric text for price, time, token, and sample counts;
- chips for states such as live, cached, frozen, waiting close, analyzing, demo, and error;
- no hero sections, marketing cards, large decorative gradients, or explanatory feature blocks.

Important numbers should be visually stronger than explanatory prose: entry, stop, take profit, R:R, confidence, historical sample count, win-rate basis, expectancy R, token usage, and cache hit rate.

## Backend API Boundary

Add a Python API package under `pa_agent/api`. It should reuse the existing `AppContext`, settings, data sources, orchestrator, records, and backtest modules.

Recommended modules:

```text
pa_agent/api/
  app.py
  context.py
  dto.py
  events.py
  routes_market.py
  routes_analysis.py
  routes_records.py
  routes_settings.py
  routes_backtest.py
```

Market APIs:

```text
GET  /api/data-sources
GET  /api/symbols?source=...
GET  /api/timeframes?source=...
GET  /api/market/snapshot?bars=100&include_forming=false
```

K-line cache APIs:

```text
GET  /api/kline-cache
POST /api/kline-cache/refresh
```

Analysis APIs:

```text
POST   /api/analysis
DELETE /api/analysis/{analysis_id}
GET    /api/analysis/{analysis_id}
GET    /api/analysis/{analysis_id}/events
```

Record and follow-up APIs:

```text
GET    /api/records
GET    /api/records/{record_id}
GET    /api/records/{record_id}/followups
POST   /api/records/{record_id}/chat
DELETE /api/chat/{chat_id}
GET    /api/chat/{chat_id}/events
```

Backtest APIs:

```text
POST /api/backtest/rebuild-setup-stats
GET  /api/backtest/setup-stats
```

Settings APIs:

```text
GET   /api/settings
PATCH /api/settings
POST  /api/settings/data-source-switch
```

Sensitive settings such as API keys, Feishu secrets, and PushPlus tokens must be masked on read and carefully handled on write.

## Communication Model

Use REST for request/response operations:

- settings;
- history;
- one-shot snapshots;
- submit/cancel task commands;
- backtest rebuild commands;
- record detail.

Use Server-Sent Events for one-way analysis streams:

- Stage 1 and Stage 2 analysis streams;
- follow-up chat streams.

Market streaming is deferred. WebSocket is not required in the first version. It can be introduced later if the app needs low-latency bidirectional control, multi-client coordination, or remote collaboration.

Analysis streaming should adapt existing `TwoStageOrchestrator.submit()` callbacks into an event queue:

```json
{ "type": "stage_started", "stage": "stage1" }
{ "type": "reasoning_delta", "stage": "stage1", "text": "..." }
{ "type": "content_delta", "stage": "stage2", "text": "..." }
{ "type": "record_saved", "record_id": "..." }
{ "type": "error", "stage": "stage2", "message": "..." }
```

Cancellation should continue to use `CancelToken`. The API layer should maintain `analysis_id -> task/token/state`.

## Frontend Stack

Recommended structure:

```text
apps/web/
  app/
  components/
  features/
    terminal/
    chart/
    analysis/
    records/
    settings/
    backtest/
    debug/
  lib/
  types/
```

Recommended libraries:

| Current PyQt Area | Web Replacement |
| --- | --- |
| PyQt6 widgets/dialogs | React + TypeScript |
| Menus and settings dialogs | Next.js routes + Radix/shadcn components |
| Local widget state | Zustand |
| Server state and polling | TanStack Query |
| Forms | react-hook-form + zod |
| QThread and Qt signals | Python background tasks + SSE queues |
| pyqtgraph K-line chart | Minimal SVG/CSS snapshot preview first; lightweight-charts only if chart parity becomes necessary |
| Auxiliary stats/decision charts | ECharts if needed |
| Modal dialogs | Radix Dialog/Popover/Tooltip |

## Chart Library Decision

Use the existing Phase 1 snapshot preview for the next analysis-first phases. Full `lightweight-charts` adoption is deferred.

Reasons to defer full chart parity:

- the Web app's near-term job is to run, inspect, save, and validate analysis;
- cached K-line previews are sufficient to verify the submitted snapshot;
- deferring chart parity avoids spending time on overlays, zoom semantics, live updates, and rendering edge cases before analysis UX exists.

Minimal chart requirements:

- render a compact, non-interactive cached snapshot preview;
- show symbol, timeframe, cache age, and bar count;
- preserve backend newest-first semantics and convert only at preview rendering;
- never use forming bars for AI analysis.

Do not use TradingView Charting Library in the analysis-first phases because licensing and integration complexity are too high. Do not use Plotly for the main chart because it is heavy for this use case. ECharts is acceptable for backtest/statistics charts later.

## Chart Compatibility Rules

The following semantics remain mandatory even with the minimal chart:

- Backend bars remain newest-first.
- The front end converts to oldest-first only at chart-rendering boundaries.
- `KlineBar.seq == 1` is the latest closed bar.
- `KlineBar.seq == 0` is the forming bar.
- AI snapshots must use closed-only bars from `build_analysis_frame` or equivalent API output.
- Live display may include the forming bar from `build_live_frame`.
- K1 should remain identifiable as the newest closed candle in analysis data, even if the preview does not label every bar.
- Entry, take profit, stop loss, and direction markers may be displayed in the decision panel instead of as chart overlays.
- Demo replay must reconstruct chart state from records without triggering live data refresh.

## Key User Flows

First open:

1. Load settings.
2. Restore last source, symbol, timeframe.
3. Load cached K-lines if available.
4. Show API-key warning if missing.
5. Disable analysis submission until required settings and bars are available.

Refresh cached snapshot:

1. Read the current configured source/symbol/timeframe.
2. Load cached K-lines or perform an explicit manual refresh.
3. Build closed-only analysis frame.
4. Display snapshot metadata and preview.

Submit analysis:

1. Freeze or snapshot the chart.
2. Build closed-only frame.
3. Decide normal vs incremental mode.
4. Start analysis task.
5. Stream Stage 1 and Stage 2 events over SSE.
6. Save record and update decision/chart overlays.
7. Enable follow-up chat.

View history:

1. Load summary rows from `records/pending`.
2. Filter by symbol, timeframe, status, action, and date.
3. Open record detail with chart snapshot, Stage 1, Stage 2, prompt/debug data.
4. Start demo replay from a selected record.

Rebuild setup statistics:

1. Run `rebuild_setup_stats_from_records()`.
2. Show scanned records, completed trades, setup buckets, skipped records, and reasons.
3. Write `config/setup_stats.json`.

## Migration Phases

### Phase 1: Local Web Shell And Read-Only API

Goal: prove the split without replacing PyQt.

Deliverables:

- FastAPI app under `pa_agent/api`;
- Next.js app under `apps/web`;
- settings read API;
- data-source metadata API;
- cached/current snapshot API;
- terminal layout shell;
- read-only chart render from snapshot;
- history summary list.

### Phase 2: Web Analysis Workbench

Goal: run and inspect the existing two-stage analysis from Web.

Deliverables:

- `POST /api/analysis` task creation from cached closed-only snapshot;
- `GET /api/analysis/{analysis_id}` task state;
- `DELETE /api/analysis/{analysis_id}` cancellation;
- `GET /api/analysis/{analysis_id}/events` SSE stream;
- Stage 1 and Stage 2 reasoning/content panels;
- decision summary panel;
- historical win-rate/sample/expectancy fields;
- token/cache metrics;
- provider, validation, cancellation, and insufficient-data errors;
- record saved indicator.

### Phase 3: History, Detail, And Follow-Up

Goal: make saved analysis inspectable and reusable from Web.

Deliverables:

- richer history filters;
- record detail page;
- Stage 1, Stage 2, prompt, strategy files, and experience sections;
- follow-up chat stream;
- demo replay from records using the minimal snapshot preview.

### Phase 4: Backtest And Statistical Feedback

Goal: expose the data-feedback layer that makes the system measurable.

Deliverables:

- rebuild setup statistics from records;
- show records scanned, trade signals, completed trades, setup buckets, and output path;
- show setup-stat rows with sample count, win rate, expectancy R, wins/losses;
- show paper gate status;
- make historical stats visible beside Stage 2 decisions.

### Phase 5: Settings And Manual Data Refresh

Goal: replace the remaining PyQt dialogs and menus.

Deliverables:

- settings pages;
- manual data refresh actions;
- notification test actions;
- debug export.

### Deferred: Full Chart Parity And Live Market Stream

Goal: only implement when analysis, history, and backtest workflows prove that richer charting is worth the complexity.

Deferred deliverables:

- `lightweight-charts` K-line rendering;
- EMA20, volume, sequence labels, support/resistance overlays;
- entry/take-profit/stop-loss chart overlays;
- market subscription API and SSE market stream;
- live refresh-age status and continuous tracking.

### Phase 6: Electron Shell

Goal: package the stable Web version as a desktop app.

Deliverables:

- Electron shell;
- Python API process startup/shutdown;
- port discovery;
- local-only access guard;
- app icon/tray behavior;
- packaging scripts.

## Testing Strategy

Python tests:

- API DTO validation;
- settings masking and patching;
- data-source switch state;
- snapshot closed/forming bar semantics;
- analysis task cancellation;
- record and follow-up loading;
- setup-statistics rebuild.

Frontend tests:

- chart preview data conversion from newest-first to oldest-first;
- closed-only analysis snapshot contract;
- settings form validation;
- state transitions for fetch, analyze, cancel, error, and replay.

Integration tests:

- SSE event ordering for Stage 1 and Stage 2;
- analysis cancellation stops backend work;
- record saved after analysis completion.

End-to-end tests with Playwright:

- app loads `/terminal`;
- fetch/read cached snapshot;
- snapshot preview renders nonblank K-lines when cached bars exist;
- submit and cancel analysis using mocked backend;
- view history and record detail;
- rebuild backtest stats;
- save settings and confirm persistence.

## Acceptance Criteria

The migration is acceptable only when:

- Web and PyQt submit equivalent closed-only K-line snapshots for the same symbol/timeframe.
- K1, forming bar, and incremental-analysis semantics remain intact.
- Stage 1 and Stage 2 stream order matches the desktop version.
- Analysis cancellation stops the backend task, not only the UI.
- Records are saved in the existing format.
- Existing JSON records can be opened by the Web history page.
- The minimal snapshot preview shows the analysis frame without changing analysis semantics.
- Settings can be read, edited, saved, and reloaded.
- API keys and notification secrets are not leaked by read APIs.
- The app remains usable with cached K-lines when the live data source is unavailable.

## Main Risks

- K-line ordering bugs between backend newest-first and chart oldest-first.
- Accidentally feeding forming bars into AI analysis.
- Race conditions between analysis stream and cancellation.
- SSE reconnect behavior hiding lost analysis events.
- Deferring chart parity too long could make visual verification weaker than PyQt for some users.
- Debug visibility becoming weaker than the current PyQt raw/debug panels.
- Electron process management creating startup or shutdown failures.

## Controller Notes

Anti's interface proposal and Hermes's architecture proposal agree on the core approach: keep Python as the domain/runtime layer, build a dense Web terminal around it, and postpone Electron until the Web architecture is proven. After Phase 1, the priority is analysis, record inspection, and backtest/statistical feedback. Full chart parity and live market streaming are explicitly deferred.
