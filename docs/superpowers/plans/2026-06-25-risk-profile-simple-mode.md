# Risk Profile Simple Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a product-facing simple risk-profile selector that maps stable Chinese labels to the existing Stage 2 decision stance and order-signal threshold.

**Architecture:** Keep `general.decision_stance` as the persisted compatibility field. Add a small backend preset helper and API endpoint so desktop, Web, and future clients share the same mapping. The first version changes only the Stage 2 stance and order-signal threshold; paper-trading gates remain advanced settings.

**Tech Stack:** Python 3.11, Pydantic, FastAPI, PyQt6, Next.js/React, Vitest, pytest.

---

### Task 1: Backend Preset Helper And API

**Files:**
- Create: `tests/unit/test_risk_profiles.py`
- Modify: `pa_agent/ai/decision_stance.py`
- Modify: `pa_agent/api/routes_settings.py`

- [ ] **Step 1: Write the failing preset helper test**

```python
from pa_agent.ai.decision_stance import RISK_PROFILE_PRESETS, apply_risk_profile
from pa_agent.config.settings import Settings


def test_apply_risk_profile_sets_stance_and_signal_threshold():
    settings = Settings()
    apply_risk_profile(settings.general, "aggressive")
    assert settings.general.decision_stance == "aggressive"
    assert settings.general.decision_confidence_threshold == RISK_PROFILE_PRESETS["aggressive"].signal_threshold
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/unit/test_risk_profiles.py::test_apply_risk_profile_sets_stance_and_signal_threshold -q`

Expected: fail because `RISK_PROFILE_PRESETS` / `apply_risk_profile` do not exist.

- [ ] **Step 3: Implement the minimal helper**

Add a frozen dataclass in `pa_agent/ai/decision_stance.py` with four presets:

```python
conservative -> signal_threshold 60
balanced -> signal_threshold 40
aggressive -> signal_threshold 30
extreme_aggressive -> signal_threshold 25
```

`apply_risk_profile(general_settings, profile)` should normalize the profile, set `decision_stance`, and set `decision_confidence_threshold`.

- [ ] **Step 4: Write the failing API test**

Add a route-level test that patches `/api/settings/risk-profile` with `{"risk_profile": "conservative"}` and expects `general.decision_stance == "conservative"` plus threshold `60`.

- [ ] **Step 5: Implement the API endpoint**

In `pa_agent/api/routes_settings.py`, add a Pydantic payload model with `risk_profile: DecisionStance`, call `apply_risk_profile`, save settings, and return `settings_to_payload`.

### Task 2: Web Selector

**Files:**
- Modify: `apps/web/types/api.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/features/terminal/terminal-workbench.tsx`
- Test: `apps/web/__tests__/terminal-workbench.test.ts`

- [ ] **Step 1: Write the failing Web test**

Assert the Terminal workbench renders a risk-profile select using the current `settings.general.decision_stance`, calls `PATCH /api/settings/risk-profile`, and reloads state after change.

- [ ] **Step 2: Implement typed API support**

Add `RiskProfile`, structured `SettingsPayload`, and `RiskProfileRequest` types. Add `api.updateRiskProfile(payload)`.

- [ ] **Step 3: Add the selector**

Add a compact selector in the top control strip with labels `稳健`, `均衡`, `进取`, `强进取`; disable it while analysis is running. Show the active threshold next to the selector using `settings.general.decision_confidence_threshold`.

### Task 3: Desktop Labels And Docs

**Files:**
- Modify: `pa_agent/gui/settings_dialog.py`
- Modify: `pa_agent/gui/general_settings_dialog.py`
- Modify: `config/settings.example.json`
- Modify: `config/README.md`

- [ ] **Step 1: Update visible labels**

Rename desktop UI label `交易倾向` to `风险档位`, use product labels, and update tooltips so users understand this is a simple-mode preset.

- [ ] **Step 2: Update examples and docs**

Document `general.decision_stance` as the risk-profile value and `general.decision_confidence_threshold` as the signal-strength threshold set by simple mode.

### Task 4: Verification

- [ ] Run focused Python tests:

```bash
python -m pytest tests/unit/test_risk_profiles.py tests/unit/test_api_routes.py tests/unit/test_settings_round_trip.py tests/unit/test_prompt_assembler.py -q
```

- [ ] Run focused Web tests:

```bash
cd apps/web
npm test -- terminal-workbench.test.ts
```

- [ ] Run type/lint checks if the package exposes them:

```bash
cd apps/web
npm run lint
```
