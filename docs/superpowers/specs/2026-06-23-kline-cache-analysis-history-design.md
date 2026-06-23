# K-Line Cache And Analysis History Design

## Problem

The GUI keeps the currently fetched K-line frame in memory. After an app restart, the chart starts empty until the selected data source returns fresh data. Source or symbol switches also reset the in-memory frame. This makes the app feel stateless even though analysis records are already persisted under `records/pending`.

Analysis records are not cleared on startup, and the existing incremental-analysis helpers can find the latest successful record for a symbol/timeframe. However, the normal GUI does not expose a concise history view, so users cannot easily see what was analyzed, when it happened, and what the result summary was.

## Decision

Add a lightweight local cache layer for fetched K-line bars and a lightweight summary index for persisted analysis records. The cache improves startup and source-switch behavior, while the history summary makes prior analysis visible in the GUI.

This should stay file-based for now. A database would add operational cost before the data model is stable.

## Scope

- Add a disk-backed K-line cache keyed by data source, symbol, and timeframe.
- Load cached bars before the first live refresh so the chart can render immediately after startup.
- Merge live bars into cached bars by timestamp, preferring newly fetched bars when duplicates exist.
- Cap retained cached bars to a configurable maximum.
- Keep analysis records as the source of truth for past analysis.
- Add a summary reader that scans persisted records and returns compact timeline rows.
- Add a GUI entry for analysis history, sorted newest first.
- Include timestamps, source/symbol/timeframe, cycle position, direction, order type, confidence, win-rate basis, sample count, and error status where available.

## Non-Goals

- Do not replace existing record files with a database.
- Do not make cached K-lines a trading signal by themselves.
- Do not automatically trust stale cache over the live data source.
- Do not rewrite the existing incremental-analysis engine.
- Do not add complex replay controls in this pass.
- Do not feed old summaries back into prompts automatically.

## Architecture

### `pa_agent/data/kline_cache.py`

Responsible for reading, writing, validating, merging, and trimming cached bars.

The cache file shape should include:

- `schema_version`
- `source`
- `symbol`
- `timeframe`
- `saved_at`
- `bars`

Bars are deduplicated by `ts_open` when present, falling back to `time`. Newer fetched bars win on conflicts. Files with mismatched metadata, invalid JSON, or unsupported schema versions are ignored.

Suggested path:

`cache/kline/{source}/{safe_symbol}_{timeframe}.json`

### `pa_agent/records/analysis_summary.py`

Responsible for scanning persisted analysis records and producing compact rows for GUI display. It should reuse the existing pending-record directory and avoid loading more text than needed where possible.

Each summary row should include:

- record timestamp
- source, symbol, timeframe
- stage status
- cycle position
- direction
- order type / action
- trade confidence
- estimated win-rate basis
- historical sample count
- error message when the record is partial or failed

### GUI Integration

Startup and source switch flow:

1. Build cache key from current source, symbol, and timeframe.
2. Load cached bars if present.
3. Render the chart with a visible cached/stale state.
4. Start the normal refresh loop.
5. On successful live refresh, merge and save cache, then render fresh state.

Analysis history flow:

1. Add a menu action or side-panel entry named "Analysis History".
2. Read summaries from persisted records.
3. Show newest-first rows.
4. Allow refresh after a new analysis finishes.

## Error Handling

- Cache read failures should not block startup.
- Cache write failures should be logged and shown only as non-blocking status text.
- Invalid cache files should be ignored.
- If live refresh fails, cached data can remain visible with a stale marker.
- Analysis-summary scan should skip corrupt records and count skipped files for diagnostics.

## Configuration

Add conservative defaults:

- `general.kline_cache_enabled = true`
- `general.kline_cache_max_bars = 2000`
- `general.analysis_history_max_rows = 200`

These settings can live in the existing settings model. A GUI toggle is optional and can be added later.

## Testing

Unit tests:

- Cache round trip preserves bars and metadata.
- Merge deduplicates bars and prefers fetched bars.
- Cache loader ignores invalid metadata and invalid JSON.
- Analysis summary extracts rows from successful and partial records.
- Summary rows sort newest first.

GUI-level smoke tests or focused unit seams:

- Main window attempts cache load before starting refresh.
- Successful refresh writes merged cache.
- Analysis history refreshes after a completed analysis.

## User-Facing Result

Restarting the app no longer makes the workspace feel blank. Previously fetched K-lines can appear immediately, then update incrementally when the selected data source responds. Prior analysis becomes visible as a timestamped history, so users can compare recent judgments without manually opening record files.
