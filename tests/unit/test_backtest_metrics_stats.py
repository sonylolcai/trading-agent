from __future__ import annotations

import pytest

from pa_agent.backtest.metrics import calculate_metrics
from pa_agent.backtest.setup_key import SetupKey
from pa_agent.backtest.simulator import TradeSimulation
from pa_agent.backtest.stats_store import SetupStatsLedger


def _result(status: str, r_multiple: float, *, triggered: bool = True) -> TradeSimulation:
    return TradeSimulation(
        status=status,
        r_multiple=r_multiple,
        entry_triggered=triggered,
        exit_price=None,
        bars_held=1 if triggered else 0,
        reason=status,
        ambiguous=False,
    )


def test_calculate_metrics_counts_only_triggered_trades_for_win_rate() -> None:
    metrics = calculate_metrics(
        [
            _result("win", 1.2),
            _result("loss", -1.0),
            _result("not_triggered", 0.0, triggered=False),
            _result("open", 0.3),
        ]
    )

    assert metrics.total_signals == 4
    assert metrics.triggered_trades == 3
    assert metrics.wins == 1
    assert metrics.losses == 1
    assert metrics.not_triggered == 1
    assert metrics.win_rate_pct == pytest.approx(50.0)
    assert metrics.expectancy_r == pytest.approx((1.2 - 1.0 + 0.3) / 3)
    assert metrics.max_drawdown_r == pytest.approx(1.0)


def test_setup_stats_ledger_exports_historical_win_rate_fields() -> None:
    key = SetupKey(
        symbol_class="crypto",
        timeframe_bucket="1h",
        cycle_position="broad_channel",
        direction="做多",
        order_type="突破单",
        primary_patterns=("wide_channel",),
        decision_stance="balanced",
    )
    ledger = SetupStatsLedger()
    ledger.record_result(key, _result("win", 1.2))
    ledger.record_result(key, _result("loss", -1.0))
    ledger.record_result(key, _result("not_triggered", 0.0, triggered=False))

    stats = ledger.stats_for(key)
    fields = ledger.historical_fields_for(key, min_sample_count=2)

    assert stats.sample_count == 2
    assert stats.win_rate_pct == pytest.approx(50.0)
    assert stats.expectancy_r == pytest.approx(0.1)
    assert fields == {
        "estimated_win_rate_basis": "historical",
        "historical_win_rate_for_this_setup": pytest.approx(50.0),
        "historical_sample_count": 2,
        "historical_expectancy_r": pytest.approx(0.1),
    }


def test_setup_stats_ledger_can_query_stage1_level_stats_before_order_type_known() -> None:
    ledger = SetupStatsLedger()
    ledger.record_result(
        SetupKey(
            symbol_class="crypto",
            timeframe_bucket="intraday_hour",
            cycle_position="broad_channel",
            direction="做多",
            order_type="突破单",
            primary_patterns=("wide_channel",),
            decision_stance="balanced",
        ),
        _result("win", 1.0),
    )
    ledger.record_result(
        SetupKey(
            symbol_class="crypto",
            timeframe_bucket="intraday_hour",
            cycle_position="broad_channel",
            direction="做多",
            order_type="限价单",
            primary_patterns=("wide_channel",),
            decision_stance="balanced",
        ),
        _result("loss", -1.0),
    )

    fields = ledger.historical_fields_for_stage1(
        symbol="BTCUSDT",
        timeframe="1h",
        stage1_diagnosis={
            "cycle_position": "broad_channel",
            "direction": "bullish",
            "detected_patterns": ["wide_channel"],
        },
        decision_stance="balanced",
        min_sample_count=2,
    )

    assert fields["estimated_win_rate_basis"] == "historical"
    assert fields["historical_sample_count"] == 2
    assert fields["historical_win_rate_for_this_setup"] == pytest.approx(50.0)
