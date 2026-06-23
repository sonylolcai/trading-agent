# Next.js Web Migration Design

## Problem

PA Agent is currently a PyQt6 desktop application. The business logic is valuable and already reasonably separated from the GUI: market data sources, K-line snapshots, two-stage AI orchestration, records, backtesting, setup statistics, and local JSON persistence all live outside most GUI widgets. The PyQt layer now carries too much application coordination: refresh loops, worker lifecycles, streaming display, chart rendering, settings dialogs, history dialogs, demo replay, and status handling.

The goal is to keep the trading and analysis behavior intact while replacing the GUI with a Web interface that can later be packaged as an Electron desktop app.

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

## Current Functional Surface

The Web version must preserve these user-facing capabilities:

- Market source selection: East Money, AkShare, Tushare, TradingView, MT5.
- Symbol, exchange, timeframe, and refresh controls.
- Live chart refresh, cached K-line recovery, forming-bar display, and closed-bar analysis snapshots.
- Manual analysis, automatic incremental analysis labeling, forced incremental analysis, wait-for-close, and continuous tracking.
- Stage 1 and Stage 2 streaming output with reasoning/content separation.
- Decision display: order type, direction, entry, take profit, stop loss, confidence, win-rate basis, sample count, and reasoning.
- Chart overlays: EMA20, sequence labels, support/resistance, entry/take-profit/stop-loss price lines, and direction markers.
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
- Top control bar: data source, exchange when relevant, symbol, timeframe, fetch data, submit/incremental analysis, wait-for-close, continuous tracking.
- Main area: chart on the left, AI/decision panel on the right.
- Bottom status bar: connection state, latest refresh age, current stage, API-key warnings, demo mode, token/cache summary.

Right-side workbench tabs:

```text
Live Stream | Decision | Decision Flow | Future Trend | Debug
```

The active tab should follow workflow state:

- Analysis running: Live Stream.
- Order opportunity: Decision or Decision Flow.
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

Important numbers should be visually stronger than explanatory prose: entry, stop, take profit, R:R, confidence, historical sample count, win-rate basis, token usage, and cache hit rate.

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
POST /api/market/subscribe
GET  /api/market/snapshot?bars=100&include_forming=false
GET  /api/market/stream
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

Use Server-Sent Events for one-way streams:

- live market frame/status stream;
- Stage 1 and Stage 2 analysis streams;
- follow-up chat streams.

WebSocket is not required in the first version. It can be introduced later if the app needs low-latency bidirectional control, multi-client coordination, or remote collaboration.

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
| pyqtgraph K-line chart | lightweight-charts |
| Auxiliary stats/decision charts | ECharts if needed |
| Modal dialogs | Radix Dialog/Popover/Tooltip |

## Chart Library Decision

Use `lightweight-charts` for the main K-line chart.

Reasons:

- strong financial-chart semantics;
- K-line and volume support;
- price lines and markers;
- fit-content behavior;
- good performance for live updates;
- smaller and more direct than Plotly;
- lower integration and licensing cost than TradingView Charting Library.

Known gaps and compensating design:

- Sequence labels such as `#1`, `#3`, `#5` should be rendered with an HTML/SVG overlay or plugin layer.
- Entry, stop, take-profit labels can use price lines plus custom side labels.
- Support/resistance zones can use overlays.
- Complex decision-tree visuals should not be forced into the K-line library; use a separate React/SVG/ECharts component.

Do not use TradingView Charting Library in the first phase because licensing and integration complexity are too high. Do not use Plotly for the main chart because it is heavy for a live terminal. ECharts is acceptable for statistics, backtest charts, or decision-flow helpers.

## Chart Compatibility Rules

The following semantics are mandatory:

- Backend bars remain newest-first.
- The front end converts to oldest-first only at chart-rendering boundaries.
- `KlineBar.seq == 1` is the latest closed bar.
- `KlineBar.seq == 0` is the forming bar.
- AI snapshots must use closed-only bars from `build_analysis_frame` or equivalent API output.
- Live display may include the forming bar from `build_live_frame`.
- K1 must appear on the rightmost closed candle.
- Odd sequence labels should be shown as in the PyQt chart.
- Entry, take profit, and stop loss lines must match the Stage 2 decision.
- Direction markers must match long/short decisions.
- Fit view should show the recent analysis window and include EMA/decision overlays in the y-range.
- Demo replay must reconstruct chart state from records without triggering live data refresh.

## Key User Flows

First open:

1. Load settings.
2. Restore last source, symbol, timeframe.
3. Load cached K-lines if available.
4. Show API-key warning if missing.
5. Disable analysis submission until required settings and bars are available.

Fetch data:

1. Subscribe selected source/symbol/timeframe.
2. Emit market stream events.
3. Update chart and refresh-age status.
4. Persist K-line cache.

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

### Phase 2: Chart Parity

Goal: match PyQt chart semantics.

Deliverables:

- `lightweight-charts` K-line rendering;
- EMA20;
- volume;
- K-line sequence labels;
- entry/take-profit/stop-loss overlays;
- support/resistance overlays;
- fit-view behavior;
- cached/live/frozen state display.

### Phase 3: Live Market Stream

Goal: replace `RefreshLoop` behavior with API-managed streaming.

Deliverables:

- market subscription API;
- SSE market stream;
- refresh-age status;
- cached fallback;
- source/symbol/timeframe switching behavior;
- no automatic analysis triggered by simple source changes.

### Phase 4: Analysis Stream

Goal: run the existing two-stage analysis from Web.

Deliverables:

- `POST /api/analysis`;
- SSE analysis events;
- cancellation;
- Stage 1 and Stage 2 live panels;
- record saving;
- decision overlays;
- token/cache metrics;
- provider and validation error display.

### Phase 5: History, Replay, Backtest, And Settings

Goal: replace the remaining PyQt dialogs and menus.

Deliverables:

- record detail page;
- follow-up chat;
- demo replay;
- backtest/setup-statistics page;
- settings pages;
- notification test actions;
- debug export.

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

- chart data conversion from newest-first to oldest-first;
- K1 rightmost closed candle contract;
- chart overlay rendering from fixed decisions;
- settings form validation;
- state transitions for fetch, analyze, cancel, error, and replay.

Integration tests:

- SSE event ordering for Stage 1 and Stage 2;
- market stream reconnect behavior;
- analysis cancellation stops backend work;
- record saved after analysis completion.

End-to-end tests with Playwright:

- app loads `/terminal`;
- switch data source and fetch snapshot;
- chart renders nonblank K-lines;
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
- Chart overlays match the PyQt chart for fixed sample records.
- Settings can be read, edited, saved, and reloaded.
- API keys and notification secrets are not leaked by read APIs.
- The app remains usable with cached K-lines when the live data source is unavailable.

## Main Risks

- K-line ordering bugs between backend newest-first and chart oldest-first.
- Accidentally feeding forming bars into AI analysis.
- Race conditions between market stream, analysis stream, and cancellation.
- SSE reconnect behavior hiding lost analysis events.
- Chart feature gaps around sequence labels and complex overlays.
- Debug visibility becoming weaker than the current PyQt raw/debug panels.
- Electron process management creating startup or shutdown failures.

## Controller Notes

Anti's interface proposal and Hermes's architecture proposal agree on the core approach: keep Python as the domain/runtime layer, build a dense Web terminal around it, and postpone Electron until the Web architecture is proven. The first implementation plan should be a narrow vertical slice, not a full GUI rewrite.
