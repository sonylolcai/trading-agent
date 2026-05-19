"""Test that ChartWidget does not draw InfiniteLine items when order_type == '不下单'.

Task 14.7 — pytest-qt test.

Validates: Requirements R9.4, R10.2
"""
from __future__ import annotations

import pytest

# Guard: skip the whole module if PyQt6 / pyqtgraph are not available
pytest.importorskip("PyQt6")
pytest.importorskip("pyqtgraph")


@pytest.fixture
def chart_widget(qtbot):
    """Create a ChartWidget and register it with qtbot."""
    from pa_agent.gui.chart_widget import ChartWidget

    widget = ChartWidget()
    qtbot.addWidget(widget)
    return widget


def _count_infinite_lines(plot_widget) -> int:
    """Count the number of InfiniteLine items currently in the plot."""
    import pyqtgraph as pg

    return sum(
        1
        for item in plot_widget.getPlotItem().items
        if isinstance(item, pg.InfiniteLine)
    )


class TestNoLinesWhenNotTrading:
    """ChartWidget must not show InfiniteLine items for '不下单' decisions."""

    def test_no_infinite_lines_after_no_order_decision(self, chart_widget):
        """set_decision with order_type='不下单' must leave zero InfiniteLine items."""
        decision = {
            "order_type": "不下单",
            "entry_price": None,
            "take_profit_price": None,
            "stop_loss_price": None,
            "reasoning": "市场结构不明朗，暂不入场。",
        }
        chart_widget.set_decision(decision)

        assert _count_infinite_lines(chart_widget) == 0, (
            "Expected no InfiniteLine items after a '不下单' decision, "
            f"but found {_count_infinite_lines(chart_widget)}."
        )

    def test_lines_cleared_when_switching_to_no_order(self, chart_widget):
        """Lines drawn for a trading decision must be cleared when '不下单' is set."""
        # First set a trading decision (should draw 3 lines)
        trading_decision = {
            "order_type": "限价单",
            "order_direction": "做多",
            "entry_price": 1900.0,
            "take_profit_price": 1920.0,
            "stop_loss_price": 1880.0,
            "reasoning": "上升趋势明确。",
        }
        chart_widget.set_decision(trading_decision)

        # Sanity check: lines should exist now
        assert _count_infinite_lines(chart_widget) > 0, (
            "Expected InfiniteLine items after a trading decision."
        )

        # Now switch to 不下单
        no_order_decision = {
            "order_type": "不下单",
            "entry_price": None,
            "take_profit_price": None,
            "stop_loss_price": None,
            "reasoning": "风险过高。",
        }
        chart_widget.set_decision(no_order_decision)

        assert _count_infinite_lines(chart_widget) == 0, (
            "Expected no InfiniteLine items after switching to '不下单', "
            f"but found {_count_infinite_lines(chart_widget)}."
        )

    def test_reset_clears_all_lines(self, chart_widget):
        """reset() must remove all InfiniteLine items."""
        trading_decision = {
            "order_type": "市价单",
            "order_direction": "做空",
            "entry_price": 1850.0,
            "take_profit_price": 1830.0,
            "stop_loss_price": 1870.0,
            "reasoning": "下降趋势。",
        }
        chart_widget.set_decision(trading_decision)
        chart_widget.reset()

        assert _count_infinite_lines(chart_widget) == 0, (
            "Expected no InfiniteLine items after reset(), "
            f"but found {_count_infinite_lines(chart_widget)}."
        )
