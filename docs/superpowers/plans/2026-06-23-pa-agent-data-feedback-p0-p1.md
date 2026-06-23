# PA Agent Data Feedback P0/P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox tracking and must be updated as work lands.

## Goal

Add the first data-feedback layer without replacing PA Agent's current strengths: the two-stage Al Brooks workflow, deterministic strategy routing, schema validation, and saved analysis records remain the core. P0 adds conservative backtesting and setup statistics. P1 improves experience replay quality and adds a paper-trading unlock check for future live-signal gating.

## Architecture

- Keep backtesting in a new `pa_agent.backtest` package so the GUI/orchestrator remains stable.
- Use existing `stage2_decision.decision` prices and `pa_agent.util.trade_metrics.compute_risk_reward()` as the single source of trade geometry.
- Treat K-line order defensively: accept newest-first or oldest-first bars, filter `closed=False`, then simulate oldest-to-newest.
- Represent historical setup context as a compact `SetupKey` built from `cycle_position`, direction, patterns, order type, timeframe, symbol class, and stance.
- Extend `ExperienceReader` in place but keep return type `list[ExperienceEntry]`.
- Prompt injection is optional: if no historical stats exist, Stage2 keeps LLM judgment and labels it as such.
- Paper-trading gate is a pure utility: it reports lock/unlock status, but does not wire into broker execution because the project does not currently auto-execute trades.

## Tech Stack

- Python dataclasses for lightweight backtest value objects.
- Pydantic settings extension for paper-trading knobs.
- Pytest unit tests first, focused on simulator, metrics/stats, experience filtering, prompt rendering, normalizer/schema, and paper gate.

## Tasks

- [x] Create failing tests for simulator order outcomes, ambiguous bars, closed-bar filtering, metrics, and setup stats.
- [x] Create failing tests for ExperienceReader outcome filtering and balanced winner/loser replay.
- [x] Create failing tests for Stage2 prompt historical stats rendering and explicit schema/normalizer fields.
- [x] Create failing tests for paper-trading unlock status.
- [x] Implement `pa_agent.backtest.simulator`, `metrics`, `setup_key`, `stats_store`, `reporter`, `engine`, and exports.
- [x] Extend `ExperienceReader.read_for_stage2()` with outcome/setup filters and balanced replay.
- [x] Render experience outcome labels in `PromptAssembler`.
- [x] Render optional historical setup stats in Stage2 prompt and document required decision fields.
- [x] Add optional historical win-rate fields to Stage2 schema and normalize them lightly.
- [x] Add paper-trading settings and pure unlock evaluator.
- [x] Run targeted tests, then a broader relevant unit subset.

## Validation

- `python -m pytest tests/unit/test_backtest_simulator.py tests/unit/test_backtest_metrics_stats.py`
- `python -m pytest tests/unit/test_experience_reader.py tests/unit/test_prompt_assembler.py`
- `python -m pytest tests/unit/test_stage2_normalizer.py tests/unit/test_paper_trading_gate.py`
- If time allows, run `python -m pytest tests/unit`

## Actual Validation

- Passed: `python -m pytest tests\unit\test_backtest_simulator.py tests\unit\test_backtest_metrics_stats.py tests\unit\test_experience_reader_quality.py tests\unit\test_stage2_historical_stats.py tests\unit\test_paper_trading_gate.py tests\unit\test_prompt_assembler.py tests\unit\test_settings_round_trip.py -q`
- Passed: `python -m compileall pa_agent\backtest pa_agent\records\experience_reader.py pa_agent\ai\prompt_assembler.py pa_agent\ai\stage2_normalizer.py pa_agent\orchestrator\two_stage.py pa_agent\config\settings.py`
- Blocked: `python -m pytest tests\unit -q` cannot collect because this environment is missing `hypothesis`.
