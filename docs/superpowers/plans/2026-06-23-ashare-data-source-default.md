# A-Share Data Source Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make East Money the default data source and expose A-share sources in the GUI.

**Architecture:** Use the existing data-source factory and data-source implementations. The GUI already builds its combo from `DATA_SOURCE_CHOICES`, so the main behavior change belongs in `pa_agent/data/factory.py`, with settings/default tests updated around it.

**Tech Stack:** Python, PyQt6 combo metadata, Pydantic settings, pytest.

---

### Task 1: Update Factory Choices and Defaults

**Files:**
- Modify: `pa_agent/data/factory.py`
- Modify: `pa_agent/config/settings.py`
- Modify: `pa_agent/app_context.py`
- Test: `tests/unit/test_data_source_factory.py`

- [x] **Step 1: Write failing tests**

Expected assertions:

```python
ui_kinds = [k for k, _ in DATA_SOURCE_CHOICES]
assert ui_kinds[:3] == ["eastmoney", "akshare", "tushare"]
assert "mt5" in ui_kinds
assert GeneralSettings().last_data_source == "eastmoney"
assert normalize_data_source_kind(None) == "eastmoney"
```

- [x] **Step 2: Run tests to verify red**

Run: `python -m pytest tests\unit\test_data_source_factory.py -q`

- [x] **Step 3: Implement minimal factory/default changes**

Set UI choices to East Money, AkShare, Tushare, TradingView, MT5. Change unknown/empty source fallback to `eastmoney`. Change `GeneralSettings.last_data_source` default to `eastmoney`. App bootstrap should also request `eastmoney` when settings are missing the field.

- [x] **Step 4: Run tests to verify green**

Run: `python -m pytest tests\unit\test_data_source_factory.py -q`

### Task 2: Update GUI Copy and A-Share Defaults

**Files:**
- Modify: `pa_agent/gui/main_window.py`
- Modify: `pa_agent/data/market_defaults.py`
- Test: `tests/unit/test_market_defaults.py`

- [x] **Step 1: Write failing tests**

Expected assertions:

```python
assert normalize_gold_symbol_for_kind("eastmoney", "XAUUSDm") == "000001"
general = {"last_data_source": "eastmoney", "last_symbol": "XAUUSDm"}
migrate_general_gold_defaults(general)
assert general["last_symbol"] == "000001"
```

- [x] **Step 2: Implement GUI copy/timeframe behavior**

Update the combo tooltip to mention A-share sources. Rename `_apply_gold_defaults_for_data_source` to generic behavior only if needed; otherwise update its docstring and include all A-share kinds for timeframe fallback.

- [x] **Step 3: Run relevant tests**

Run: `python -m pytest tests\unit\test_data_source_factory.py tests\unit\test_market_defaults.py -q`

### Task 3: Verification

- [x] Run targeted tests.
- [x] Run `python -m compileall` for touched app modules.
- [x] Run `git diff --check`.

## Actual Validation

- Passed: `python -m pytest tests\unit\test_data_source_factory.py tests\unit\test_market_defaults.py::test_ashare_kinds_rewrite_gold_symbol_to_ashare_default tests\unit\test_market_defaults.py::test_migrate_general_missing_source_defaults_to_eastmoney_ashare -q`
- Passed: `python -m pytest tests\unit\test_settings_round_trip.py tests\unit\test_data_source_factory.py -q`
- Passed: `python -m pytest tests\unit\test_backtest_record_replay.py tests\unit\test_backtest_simulator.py tests\unit\test_backtest_metrics_stats.py tests\unit\test_stage2_historical_stats.py -q`
- Passed: `python -m compileall pa_agent\backtest pa_agent\gui\main_window.py`
- Manual smoke: `rebuild_setup_stats_from_records()` scanned current records and wrote `config/setup_stats.json`.
