"""Read-only dialog for browsing saved analysis summaries."""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pa_agent.records.analysis_summary import AnalysisSummary


class AnalysisHistoryDialog(QDialog):
    HEADERS = [
        "时间",
        "数据源",
        "标的",
        "周期",
        "状态",
        "周期位置",
        "方向",
        "动作",
        "信心",
        "胜率依据",
        "样本",
        "异常",
    ]

    def __init__(
        self,
        summaries: list[AnalysisSummary],
        *,
        refresh: Callable[[], list[AnalysisSummary]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._refresh = refresh
        self.setWindowTitle("分析历史")
        self.resize(1180, 540)

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(self.HEADERS), self)
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        if self._refresh is not None:
            refresh_btn = buttons.addButton("刷新", QDialogButtonBox.ButtonRole.ActionRole)
            refresh_btn.clicked.connect(self._on_refresh_clicked)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.set_summaries(summaries)

    def set_summaries(self, summaries: list[AnalysisSummary]) -> None:
        self._table.setRowCount(len(summaries))
        for row_index, summary in enumerate(summaries):
            values = [
                summary.timestamp_local_iso,
                summary.source,
                summary.symbol,
                summary.timeframe,
                summary.status,
                summary.cycle_position,
                summary.direction,
                summary.order_type,
                "" if summary.trade_confidence is None else str(summary.trade_confidence),
                summary.win_rate_basis,
                "" if summary.historical_sample_count is None else str(summary.historical_sample_count),
                summary.error_message,
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row_index, col_index, item)

    def _on_refresh_clicked(self) -> None:
        if self._refresh is None:
            return
        self.set_summaries(self._refresh())
