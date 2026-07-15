# Risk Profile Aware Rolling Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/api/backtest/rolling-summary` respond to the selected risk profile, so aggressive profiles produce more proxy trade signals and visibly different rolling backtest metrics.

**Architecture:** Keep saved-record replay unchanged because it replays decisions already made at the time of each record. Add a small risk-profile preset layer to the deterministic rolling backtest proxy, pass the current API settings into it, and return the active profile in the payload so the frontend can make the behavior clear.

**Tech Stack:** Python 3.11, FastAPI, pytest, Next.js, React, TypeScript, Vitest.

---

## Current Evidence

- `config/settings.json` has `general.decision_stance = "aggressive"` and `decision_confidence_threshold = 30`, so setting persistence is working.
- Latest saved analysis record uses `aggressive / 30`, so new AI analysis receives the profile.
- `pa_agent/api/routes_backtest.py` currently calls `build_rolling_summary(...)` without a profile argument.
- `pa_agent/backtest/rolling.py` uses fixed constants (`LOOKBACK_BARS = 5`, `TARGET_R = 1.2`) and fixed setup filters, so rolling summary cannot change when the risk profile changes.
- `pa_agent/backtest/record_replay.py` intentionally does not call the LLM; it replays saved `stage2_decision` values and buckets by `record.meta.decision_stance`. Leave this behavior alone.

## Ownership Split

Antigravity should own backend behavior and Python tests.

Hermes CLI should own frontend display, TypeScript types, and frontend tests after the backend payload shape is clear. If Hermes starts before backend lands, it should implement against the payload contract in this plan and keep changes scoped.

---

### Task 1: Backend Rolling Risk Profile Presets

**Files:**
- Modify: `pa_agent/backtest/rolling.py`
- Test: `tests/unit/test_backtest_rolling.py`

- [ ] **Step 1: Add a failing test proving profiles change signal frequency**

Add this test to `tests/unit/test_backtest_rolling.py`:

```python
def _choppy_uptrend_bars(count: int) -> list[KlineBar]:
    closes = []
    value = 100.0
    pattern = (0.35, -0.12, 0.34, -0.08, 0.33, 0.18)
    for index in range(count):
        value += pattern[index % len(pattern)]
        closes.append(round(value, 4))
    oldest_first = [
        _custom_bar(
            i,
            open_=close - 0.12,
            high=close + 0.18,
            low=close - 0.72,
            close=close,
            seq=count - i,
        )
        for i, close in enumerate(closes)
    ]
    return list(reversed(oldest_first))


def test_rolling_summary_risk_profile_changes_trade_frequency() -> None:
    bars = _choppy_uptrend_bars(80)

    conservative = build_rolling_summary(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=bars,
        window=80,
        risk_profile="conservative",
    ).to_payload()
    aggressive = build_rolling_summary(
        source="eastmoney",
        symbol="000001",
        timeframe="1h",
        bars=bars,
        window=80,
        risk_profile="aggressive",
    ).to_payload()

    assert conservative["risk_profile"] == "conservative"
    assert aggressive["risk_profile"] == "aggressive"
    assert aggressive["trade_signals"] > conservative["trade_signals"]
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
pytest tests/unit/test_backtest_rolling.py::test_rolling_summary_risk_profile_changes_trade_frequency -q
```

Expected: fail because `build_rolling_summary()` does not accept `risk_profile`, or the payload has no `risk_profile`.

- [ ] **Step 3: Add profile presets to `pa_agent/backtest/rolling.py`**

Add a frozen dataclass near the constants:

```python
@dataclass(frozen=True)
class RollingRiskPreset:
    profile: str
    min_directional_moves: int
    min_net_range_multiple: float
    require_followthrough: bool
    risk_range_multiplier: float
    target_r: float


ROLLING_RISK_PRESETS: dict[str, RollingRiskPreset] = {
    "conservative": RollingRiskPreset(
        profile="conservative",
        min_directional_moves=LOOKBACK_BARS - 1,
        min_net_range_multiple=0.5,
        require_followthrough=True,
        risk_range_multiplier=0.75,
        target_r=1.2,
    ),
    "balanced": RollingRiskPreset(
        profile="balanced",
        min_directional_moves=3,
        min_net_range_multiple=0.35,
        require_followthrough=True,
        risk_range_multiplier=0.65,
        target_r=1.25,
    ),
    "aggressive": RollingRiskPreset(
        profile="aggressive",
        min_directional_moves=2,
        min_net_range_multiple=0.2,
        require_followthrough=False,
        risk_range_multiplier=0.55,
        target_r=1.35,
    ),
    "extreme_aggressive": RollingRiskPreset(
        profile="extreme_aggressive",
        min_directional_moves=2,
        min_net_range_multiple=0.1,
        require_followthrough=False,
        risk_range_multiplier=0.45,
        target_r=1.5,
    ),
}
```

Add:

```python
def _resolve_risk_preset(risk_profile: str | None) -> RollingRiskPreset:
    try:
        from pa_agent.ai.decision_stance import normalize_stance

        key = normalize_stance(risk_profile)
    except Exception:
        key = "conservative"
    return ROLLING_RISK_PRESETS.get(key, ROLLING_RISK_PRESETS["conservative"])
```

- [ ] **Step 4: Thread the preset through the rolling algorithm**

Change signatures and call sites:

```python
def _momentum_direction(context: list[KlineBar], preset: RollingRiskPreset) -> str | None:
```

Inside `_momentum_direction`, replace fixed thresholds with:

```python
if up_moves >= preset.min_directional_moves and net_change > avg_range * preset.min_net_range_multiple:
    return "long"
if down_moves >= preset.min_directional_moves and -net_change > avg_range * preset.min_net_range_multiple:
    return "short"
```

Change followthrough handling in the main loop:

```python
if preset.require_followthrough and not _has_followthrough(direction, prior, signal):
    skipped_no_followthrough += 1
    continue
```

Change `_breakout_decision` signature:

```python
def _breakout_decision(
    direction: str,
    signal: KlineBar,
    avg_range: float,
    preset: RollingRiskPreset,
) -> dict[str, object]:
```

Replace `avg_range * 0.75` with `avg_range * preset.risk_range_multiplier` and replace `TARGET_R` with `preset.target_r`.

- [ ] **Step 5: Add profile fields to summary payload**

Add `risk_profile: str` to `RollingBacktestSummary`.

In `to_payload()`, include:

```python
"risk_profile": self.risk_profile,
```

Update `_empty_summary(...)` to accept `risk_profile: str = "conservative"` and pass it to the dataclass.

Update `build_rolling_summary(...)` signature:

```python
def build_rolling_summary(
    *,
    source: str,
    symbol: str,
    timeframe: str,
    bars: Iterable[KlineBar],
    window: int = 100,
    risk_profile: str | None = None,
) -> RollingBacktestSummary:
```

At the start of the function:

```python
preset = _resolve_risk_preset(risk_profile)
```

Use `preset.profile` for all returned summaries.

- [ ] **Step 6: Run backend rolling tests**

Run:

```powershell
pytest tests/unit/test_backtest_rolling.py -q
```

Expected: all tests pass.

---

### Task 2: API Route Uses Current Settings

**Files:**
- Modify: `pa_agent/api/routes_backtest.py`
- Test: `tests/unit/test_api_backtest_routes.py`

- [ ] **Step 1: Add a route test for active profile propagation**

Add to `tests/unit/test_api_backtest_routes.py`:

```python
def test_rolling_summary_route_uses_current_risk_profile(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.settings.general.decision_stance = "aggressive"
    context.kline_cache.write(
        "eastmoney",
        "000001",
        "1h",
        _rising_bars(36),
        max_bars=2000,
    )
    client = TestClient(create_app(context))

    response = client.get("/api/backtest/rolling-summary?window=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_profile"] == "aggressive"
```

- [ ] **Step 2: Run the focused API test and verify it fails**

Run:

```powershell
pytest tests/unit/test_api_backtest_routes.py::test_rolling_summary_route_uses_current_risk_profile -q
```

Expected: fail until the route passes the profile and the payload includes it.

- [ ] **Step 3: Pass `ctx.settings.general.decision_stance` into `build_rolling_summary`**

In `pa_agent/api/routes_backtest.py`, update the call:

```python
summary = build_rolling_summary(
    source=selected_source,
    symbol=selected_symbol,
    timeframe=selected_timeframe,
    bars=entry.bars if entry is not None else (),
    window=window,
    risk_profile=getattr(ctx.settings.general, "decision_stance", None),
)
```

- [ ] **Step 4: Run API backtest tests**

Run:

```powershell
pytest tests/unit/test_api_backtest_routes.py -q
```

Expected: all tests pass.

---

### Task 3: Frontend Types and Dashboard Copy

**Files:**
- Modify: `apps/web/types/api.ts`
- Modify: `apps/web/features/terminal/terminal-workbench.tsx`
- Test: `apps/web/__tests__/terminal-workbench.test.ts`

- [ ] **Step 1: Add payload type field**

In `apps/web/types/api.ts`, add to `RollingBacktestResponse`:

```ts
risk_profile?: string;
```

- [ ] **Step 2: Show the active backtest profile in the rolling dashboard**

In `RollingBacktestDashboard`, add a local:

```ts
const profile = data?.risk_profile ?? 'n/a';
```

Change the subtitle from:

```tsx
? `${data.symbol} ${data.timeframe} / ${data.bar_count} bars / ${data.evaluated_windows} windows`
```

to:

```tsx
? `${data.symbol} ${data.timeframe} / ${data.bar_count} bars / ${data.evaluated_windows} windows / ${profile}`
```

Keep copy short. Do not add explanatory marketing text. The goal is just to make the active profile visible.

- [ ] **Step 3: Add or update frontend test**

In `apps/web/__tests__/terminal-workbench.test.ts`, ensure the mocked rolling backtest response includes:

```ts
risk_profile: 'aggressive',
```

Add an assertion:

```ts
expect(html).toContain('aggressive');
```

- [ ] **Step 4: Run frontend focused tests**

Run in `apps/web`:

```powershell
npm test -- --run __tests__/terminal-workbench.test.ts
```

Expected: test passes.

- [ ] **Step 5: Run frontend typecheck**

Run in `apps/web`:

```powershell
npm run typecheck
```

Expected: no TypeScript errors.

---

### Task 4: Documentation Note

**Files:**
- Modify: `README.md`
- Modify: `CandleCast使用文档.md`

- [ ] **Step 1: Clarify current behavior**

Add a short note near the rolling backtest documentation:

```markdown
滚动回测会读取当前风险档位，并用该档位调整确定性代理信号的触发门槛、跟随确认要求和目标 R。历史 setup 统计不会重跑旧 AI 决策；它只回放已保存记录中的当时决策，并按记录中的风险档位分桶。
```

- [ ] **Step 2: Verify docs diff is scoped**

Run:

```powershell
git diff -- README.md CandleCast使用文档.md
```

Expected: only the short behavior clarification is added.

---

## Final Verification

Run:

```powershell
pytest tests/unit/test_backtest_rolling.py tests/unit/test_api_backtest_routes.py -q
```

Run in `apps/web`:

```powershell
npm test -- --run __tests__/terminal-workbench.test.ts
npm run typecheck
```

Manual check:

1. Set risk profile to `conservative`, refresh rolling summary, record `trade_signals`.
2. Set risk profile to `aggressive`, refresh rolling summary, verify `risk_profile` is `aggressive`.
3. On a choppy trend cache, verify aggressive has more `trade_signals` than conservative.

## Non-Goals

- Do not make saved-record replay regenerate historical AI decisions.
- Do not call the LLM inside rolling backtest.
- Do not change Stage 2 prompt behavior; it already receives the risk profile.
- Do not refactor unrelated Chinese encoding or UI copy.
