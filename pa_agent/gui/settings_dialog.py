"""Settings dialog for PA Agent — edits all Settings fields via a form."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt

from pa_agent.config.settings import Settings, save_settings
from pa_agent.config.paths import SETTINGS_JSON_PATH


class SettingsDialog(QDialog):
    """Modal dialog that exposes all Settings fields as editable form widgets.

    On save, calls ``save_settings(settings, SETTINGS_JSON_PATH)`` and closes.
    The api_key field uses Password echo mode by default; a "显示" toggle button
    temporarily reveals the plaintext — this toggle never triggers a save.
    The plaintext key is NEVER shown in a QLabel.
    """

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(520)
        self._settings = settings
        self._setup_ui()
        self._load_values()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)

        # Scrollable area so the form fits on small screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        form_layout = QVBoxLayout(container)
        form_layout.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(container)
        root_layout.addWidget(scroll)

        # ── AI Provider group ─────────────────────────────────────────────────
        provider_group = QGroupBox("AI 提供商")
        provider_form = QFormLayout(provider_group)

        self._model_edit = QLineEdit()
        provider_form.addRow("模型 (model):", self._model_edit)

        self._base_url_edit = QLineEdit()
        provider_form.addRow("Base URL:", self._base_url_edit)

        # api_key row: QLineEdit (Password) + "显示" toggle button
        api_key_row = QHBoxLayout()
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("输入 API Key")
        api_key_row.addWidget(self._api_key_edit)
        self._show_key_btn = QPushButton("显示")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.setFixedWidth(52)
        self._show_key_btn.toggled.connect(self._toggle_api_key_visibility)
        api_key_row.addWidget(self._show_key_btn)
        provider_form.addRow("API Key:", api_key_row)

        self._thinking_check = QCheckBox("启用 Thinking")
        provider_form.addRow("Thinking:", self._thinking_check)

        self._reasoning_effort_combo = QComboBox()
        self._reasoning_effort_combo.addItems(["low", "medium", "high", "max"])
        provider_form.addRow("Reasoning Effort:", self._reasoning_effort_combo)

        self._context_window_spin = QSpinBox()
        self._context_window_spin.setRange(1_000, 2_000_000)
        self._context_window_spin.setSingleStep(1_000)
        provider_form.addRow("Context Window:", self._context_window_spin)

        form_layout.addWidget(provider_group)

        # ── Pricing group ─────────────────────────────────────────────────────
        pricing_group = QGroupBox("定价 (¥/M tokens)")
        pricing_form = QFormLayout(pricing_group)

        self._input_cache_hit_spin = QDoubleSpinBox()
        self._input_cache_hit_spin.setRange(0.0, 10_000.0)
        self._input_cache_hit_spin.setDecimals(4)
        self._input_cache_hit_spin.setSingleStep(0.01)
        pricing_form.addRow("Input Cache Hit:", self._input_cache_hit_spin)

        self._input_cache_miss_spin = QDoubleSpinBox()
        self._input_cache_miss_spin.setRange(0.0, 10_000.0)
        self._input_cache_miss_spin.setDecimals(4)
        self._input_cache_miss_spin.setSingleStep(0.1)
        pricing_form.addRow("Input Cache Miss:", self._input_cache_miss_spin)

        self._output_spin = QDoubleSpinBox()
        self._output_spin.setRange(0.0, 10_000.0)
        self._output_spin.setDecimals(4)
        self._output_spin.setSingleStep(0.1)
        pricing_form.addRow("Output:", self._output_spin)

        form_layout.addWidget(pricing_group)

        # ── General group ─────────────────────────────────────────────────────
        general_group = QGroupBox("通用设置")
        general_form = QFormLayout(general_group)

        self._default_bar_count_spin = QSpinBox()
        self._default_bar_count_spin.setRange(2, 5_000)
        general_form.addRow("默认 Bar 数量:", self._default_bar_count_spin)

        self._refresh_interval_spin = QSpinBox()
        self._refresh_interval_spin.setRange(100, 10_000)
        self._refresh_interval_spin.setSuffix(" ms")
        general_form.addRow("刷新间隔:", self._refresh_interval_spin)

        self._cost_warning_spin = QSpinBox()
        self._cost_warning_spin.setRange(1, 100)
        self._cost_warning_spin.setSuffix(" %")
        general_form.addRow("费用警告阈值:", self._cost_warning_spin)

        self._last_symbol_edit = QLineEdit()
        general_form.addRow("上次品种:", self._last_symbol_edit)

        self._last_timeframe_edit = QLineEdit()
        general_form.addRow("上次周期:", self._last_timeframe_edit)

        self._last_htf_text_edit = QPlainTextEdit()
        self._last_htf_text_edit.setFixedHeight(80)
        general_form.addRow("上次 HTF 文本:", self._last_htf_text_edit)

        form_layout.addWidget(general_group)

        # ── Dialog buttons ────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

    # ── Value loading / saving ────────────────────────────────────────────────

    def _load_values(self) -> None:
        """Populate all widgets from the current Settings object."""
        p = self._settings.provider
        g = self._settings.general

        self._model_edit.setText(p.model)
        self._base_url_edit.setText(p.base_url)
        self._api_key_edit.setText(p.api_key)
        self._thinking_check.setChecked(p.thinking)

        idx = self._reasoning_effort_combo.findText(p.reasoning_effort)
        if idx >= 0:
            self._reasoning_effort_combo.setCurrentIndex(idx)

        self._context_window_spin.setValue(p.context_window)
        self._input_cache_hit_spin.setValue(p.pricing.input_cache_hit)
        self._input_cache_miss_spin.setValue(p.pricing.input_cache_miss)
        self._output_spin.setValue(p.pricing.output)

        self._default_bar_count_spin.setValue(g.default_bar_count)
        self._refresh_interval_spin.setValue(g.refresh_interval_ms)
        self._cost_warning_spin.setValue(int(g.cost_warning_threshold_pct))
        self._last_symbol_edit.setText(g.last_symbol)
        self._last_timeframe_edit.setText(g.last_timeframe)
        self._last_htf_text_edit.setPlainText(g.last_htf_text)

    def _on_save(self) -> None:
        """Write widget values back to the Settings object and persist to disk."""
        p = self._settings.provider
        g = self._settings.general

        p.model = self._model_edit.text().strip()
        p.base_url = self._base_url_edit.text().strip()
        p.api_key = self._api_key_edit.text()
        p.thinking = self._thinking_check.isChecked()
        p.reasoning_effort = self._reasoning_effort_combo.currentText()  # type: ignore[assignment]
        p.context_window = self._context_window_spin.value()
        p.pricing.input_cache_hit = self._input_cache_hit_spin.value()
        p.pricing.input_cache_miss = self._input_cache_miss_spin.value()
        p.pricing.output = self._output_spin.value()

        g.default_bar_count = self._default_bar_count_spin.value()
        g.refresh_interval_ms = self._refresh_interval_spin.value()
        g.cost_warning_threshold_pct = float(self._cost_warning_spin.value())
        g.last_symbol = self._last_symbol_edit.text().strip()
        g.last_timeframe = self._last_timeframe_edit.text().strip()
        g.last_htf_text = self._last_htf_text_edit.toPlainText()

        save_settings(self._settings, SETTINGS_JSON_PATH)
        self.accept()

    # ── Toggle helpers ────────────────────────────────────────────────────────

    def _toggle_api_key_visibility(self, checked: bool) -> None:
        """Toggle api_key echo mode between Password and Normal.

        This does NOT trigger a save — it is purely a display convenience.
        The plaintext key is never placed in any QLabel.
        """
        if checked:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("隐藏")
        else:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("显示")
