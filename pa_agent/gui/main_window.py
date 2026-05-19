"""Main application window for PA Agent."""
from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from pa_agent.app_context import AppContext

logger = logging.getLogger(__name__)

# Zombie timeout in milliseconds (5 seconds)
_WORKER_JOIN_TIMEOUT_MS = 5000


# ── AI Worker ─────────────────────────────────────────────────────────────────

class _AnalysisWorker(QThread):
    """Runs TwoStageOrchestrator.submit() on a background thread.

    Signals
    -------
    finished(dict):
        Emitted with the stage2_decision dict on success (or empty dict on
        failure / cancellation).
    status_update(str):
        Emitted with human-readable progress text.
    """

    finished = pyqtSignal(dict)
    status_update = pyqtSignal(str)

    def __init__(
        self,
        orchestrator: Any,
        frame: Any,
        htf_text: str,
        cancel_token: Any,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._orchestrator = orchestrator
        self._frame = frame
        self._htf_text = htf_text
        self._cancel_token = cancel_token

    def run(self) -> None:
        from pa_agent.util.threading import OrchestratorEvent

        _EVENT_LABELS = {
            OrchestratorEvent.Stage1Started: "阶段一分析中…",
            OrchestratorEvent.Stage1Done: "阶段一完成",
            OrchestratorEvent.Stage2Started: "阶段二分析中…",
            OrchestratorEvent.Stage2Done: "阶段二完成",
            OrchestratorEvent.RecordSaved: "记录已保存",
            OrchestratorEvent.Cancelled: "已取消",
            OrchestratorEvent.Stage1Failed: "阶段一失败",
            OrchestratorEvent.Stage2Failed: "阶段二失败",
        }

        def on_event(event: OrchestratorEvent) -> None:
            label = _EVENT_LABELS.get(event, str(event))
            self.status_update.emit(label)

        try:
            record = self._orchestrator.submit(
                self._frame,
                self._htf_text,
                self._cancel_token,
                on_event,
            )
            decision = record.stage2_decision or {}
        except Exception as exc:  # noqa: BLE001
            logger.error("Analysis worker error: %s", exc, exc_info=True)
            decision = {}

        self.finished.emit(decision)


# ── MainWindow ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Top-level window with a three-tab layout and a status bar.

    Tabs
    ----
    0 — 主页    (home / chart + analysis)
    1 — 对话页  (conversation / free-chat)
    2 — 调试页  (debug / raw AI output)
    """

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PA Agent")
        self.resize(1280, 800)
        self._ctx = ctx
        self._worker: _AnalysisWorker | None = None
        self._cancel_token: Any = None
        self._analysis_in_progress = False
        self._switching = False
        self._free_chat_session: Any = None
        # RefreshLoop runs in its own QThread
        self._refresh_loop: Any = None
        self._refresh_thread: QThread | None = None
        self._setup_ui()
        self._connect_event_bus()
        self._start_refresh_loop()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        # ── Tab widget ────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._home_tab = self._build_home_tab()
        self._chat_tab = QWidget()
        self._debug_tab = QWidget()

        self._tabs.addTab(self._home_tab, "主页")
        self._tabs.addTab(self._chat_tab, "对话页")
        self._tabs.addTab(self._debug_tab, "调试页")

        self.setCentralWidget(self._tabs)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")

        # ── Menu bar ──────────────────────────────────────────────────────────
        menu_bar: QMenuBar = self.menuBar()  # type: ignore[assignment]
        settings_menu = menu_bar.addMenu("设置")

        open_settings_action = QAction("打开设置…", self)
        open_settings_action.triggered.connect(self._open_settings_dialog)
        settings_menu.addAction(open_settings_action)

    def _build_home_tab(self) -> QWidget:
        """Build and return the home tab widget."""
        from pa_agent.gui.chart_widget import ChartWidget
        from pa_agent.gui.decision_panel import DecisionPanel

        tab = QWidget()
        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(6)

        # ── Control bar ───────────────────────────────────────────────────────
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)

        # Symbol
        ctrl_layout.addWidget(QLabel("品种:"))
        self._symbol_combo = QComboBox()
        self._symbol_combo.addItems(["XAUUSD", "EURUSD", "BTCUSD"])
        self._symbol_combo.setMinimumWidth(90)
        ctrl_layout.addWidget(self._symbol_combo)

        # Timeframe
        ctrl_layout.addWidget(QLabel("周期:"))
        self._tf_combo = QComboBox()
        self._tf_combo.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        self._tf_combo.setCurrentText("1h")
        self._tf_combo.setMinimumWidth(60)
        ctrl_layout.addWidget(self._tf_combo)
        # Bar count
        ctrl_layout.addWidget(QLabel("K线数:"))
        self._bar_count_spin = QSpinBox()
        self._bar_count_spin.setRange(2, 5000)
        self._bar_count_spin.setValue(200)
        self._bar_count_spin.setMinimumWidth(70)
        ctrl_layout.addWidget(self._bar_count_spin)

        ctrl_layout.addStretch()

        # Submit button
        self._submit_btn = QPushButton("提交分析")
        self._submit_btn.setMinimumWidth(100)
        self._submit_btn.clicked.connect(self._on_submit_analysis)
        ctrl_layout.addWidget(self._submit_btn)

        outer_layout.addLayout(ctrl_layout)

        # ── HTF text area ─────────────────────────────────────────────────────
        htf_label = QLabel("高时间框架描述 (HTF):")
        outer_layout.addWidget(htf_label)

        self._htf_edit = QPlainTextEdit()
        self._htf_edit.setPlaceholderText("请输入高时间框架市场背景描述…")
        self._htf_edit.setMaximumHeight(80)
        outer_layout.addWidget(self._htf_edit)

        # ── Chart + Decision splitter ─────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._chart_widget = ChartWidget()
        self._chart_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        splitter.addWidget(self._chart_widget)

        self._decision_panel = DecisionPanel()
        self._decision_panel.setMinimumWidth(220)
        self._decision_panel.setMaximumWidth(360)
        splitter.addWidget(self._decision_panel)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        outer_layout.addWidget(splitter, stretch=1)

        # Initial button state
        self._update_submit_button_state()

        # Connect symbol/timeframe combo boxes to the switch handler
        self._symbol_combo.currentTextChanged.connect(
            lambda _: self._on_symbol_or_tf_changed(
                self._symbol_combo.currentText(), self._tf_combo.currentText()
            )
        )
        self._tf_combo.currentTextChanged.connect(
            lambda _: self._on_symbol_or_tf_changed(
                self._symbol_combo.currentText(), self._tf_combo.currentText()
            )
        )

        return tab

    def _connect_event_bus(self) -> None:
        """Wire EventBus signals to status bar and tab slots (if bus is ready)."""
        bus = self._ctx.event_bus
        if bus is None:
            return
        bus.status.connect(self._on_status_update)

        # Wire data_frame signal to chart widget if available
        if hasattr(bus, "data_frame"):
            bus.data_frame.connect(self._on_data_frame)

    def _start_refresh_loop(self) -> None:
        """Start the RefreshLoop in a dedicated QThread if data_source is available."""
        data_source = getattr(self._ctx, "data_source", None)
        buffer = getattr(self._ctx, "buffer", None)
        if data_source is None or buffer is None:
            logger.debug("RefreshLoop not started: data_source or buffer not available")
            return

        from pa_agent.data.refresh_loop import RefreshLoop
        from pa_agent.util.threading import CancelToken

        settings = getattr(self._ctx, "settings", None)
        interval_ms = 1000
        n_bars = 200
        if settings is not None:
            interval_ms = getattr(settings.general, "refresh_interval_ms", 1000)
            n_bars = getattr(settings.general, "default_bar_count", 200)

        self._refresh_cancel_token = CancelToken()
        self._refresh_loop = RefreshLoop(
            data_source=data_source,
            buffer=buffer,
            n_bars=n_bars,
            interval_ms=interval_ms,
            cancel_token=self._refresh_cancel_token,
        )

        # Wire RefreshLoop signals
        self._refresh_loop.frame_ready.connect(self._on_refresh_frame_ready)
        self._refresh_loop.status_changed.connect(self._on_status_update)

        # Wire to event bus if available
        bus = self._ctx.event_bus
        if bus is not None:
            self._refresh_loop.frame_ready.connect(bus.emit_data_frame)
            self._refresh_loop.status_changed.connect(bus.emit_status)

        self._refresh_loop.start()
        logger.debug("RefreshLoop started")

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_status_update(self, text: str) -> None:
        """Update the status bar with subscription / analysis / data-delay text."""
        self._status_bar.showMessage(text)

    def _on_data_frame(self, frame: Any) -> None:
        """Forward a new KlineFrame to the chart widget (throttled by 30 Hz timer)."""
        self._chart_widget.set_frame(frame)

    def _on_refresh_frame_ready(self, bars: Any) -> None:
        """Handle frame_ready signal from RefreshLoop (raw bar list)."""
        # The RefreshLoop emits a list of bars; we forward via the event bus
        # or directly update the chart if the bus is not available.
        bus = self._ctx.event_bus
        if bus is None:
            # Direct path: build a minimal frame and push to chart
            # (full KlineFrame building happens in snapshot; here we just
            # update the buffer which the chart reads via its 30Hz timer)
            pass

    def _on_symbol_or_tf_changed(self, new_symbol: str, new_tf: str) -> None:
        """Handle symbol or timeframe combo box change.

        Steps (design §B.10, R3.1–R3.5):
        1. Cancel current AI worker and wait up to 5 s (zombie if timeout).
        2. Save partial record if analysis was in progress.
        3. Unsubscribe data source, clear buffer, re-subscribe.
        4. Reset ChartWidget.
        5. Destroy FreeChatSession, disable Tab2 input.
        6. Reset or preserve ledger based on settings.
        """
        if self._switching:
            return  # Prevent re-entrant calls

        self._switching = True
        try:
            # ── Step 1: Cancel current AI worker ─────────────────────────────
            if self._worker is not None and self._worker.isRunning():
                if self._cancel_token is not None:
                    self._cancel_token.set()
                finished = self._worker.wait(_WORKER_JOIN_TIMEOUT_MS)
                if not finished:
                    logger.warning(
                        "AI worker did not finish within %d ms after symbol/tf switch; "
                        "marking as zombie",
                        _WORKER_JOIN_TIMEOUT_MS,
                    )
                    # Mark as zombie — do not force-kill
                self._worker = None

            # ── Step 2: Save partial record if analysis was in progress ───────
            if self._analysis_in_progress:
                pending_writer = getattr(self._ctx, "pending_writer", None)
                if pending_writer is not None:
                    # We don't have the active record here; the orchestrator
                    # handles save_partial via the cancel token path.
                    # This is a belt-and-suspenders call for any record that
                    # may have been built but not yet saved.
                    try:
                        pending_writer.save_partial(None, reason="user_switched")
                    except Exception:  # noqa: BLE001
                        pass
                self._analysis_in_progress = False
                self._update_submit_button_state()

            # ── Step 3: Unsubscribe, clear buffer, re-subscribe ───────────────
            data_source = getattr(self._ctx, "data_source", None)
            buffer = getattr(self._ctx, "buffer", None)
            if data_source is not None:
                try:
                    data_source.unsubscribe()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("unsubscribe failed: %s", exc)
            if buffer is not None:
                buffer.clear()
            if data_source is not None:
                try:
                    data_source.subscribe(new_symbol, new_tf)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("subscribe(%s, %s) failed: %s", new_symbol, new_tf, exc)

            # ── Step 4: Reset ChartWidget ─────────────────────────────────────
            if hasattr(self, "_chart_widget"):
                self._chart_widget.reset()

            # ── Step 5: Destroy FreeChatSession, disable Tab2 input ───────────
            self._free_chat_session = None
            self._disable_chat_input()

            # ── Step 6: Reset ledger (always reset on symbol/tf switch) ───────
            ledger = getattr(self._ctx, "ledger", None)
            if ledger is not None:
                try:
                    ledger.reset()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("ledger.reset() failed: %s", exc)

            self._status_bar.showMessage(f"已切换至 {new_symbol} {new_tf}")
            logger.info("Symbol/TF switched to %s %s", new_symbol, new_tf)

        finally:
            self._switching = False

    def _disable_chat_input(self) -> None:
        """Disable the Tab2 free-chat input widget if it exists."""
        # The ConversationWidget is in Tab2; try to find and disable its input.
        chat_tab = self._tabs.widget(1)
        if chat_tab is None:
            return
        # Look for QPlainTextEdit children (the input box)
        from PyQt6.QtWidgets import QPlainTextEdit as _PTE
        for child in chat_tab.findChildren(_PTE):
            child.setEnabled(False)
            break

    def _on_submit_analysis(self) -> None:
        """Handle the '提交分析' button click."""
        if not self._can_submit():
            return

        # Cancel any existing worker before starting a new one
        if self._worker is not None and self._worker.isRunning():
            if self._cancel_token is not None:
                self._cancel_token.set()
            self._worker.wait(_WORKER_JOIN_TIMEOUT_MS)
            self._worker = None

        # Gather inputs
        symbol = self._symbol_combo.currentText()
        timeframe = self._tf_combo.currentText()
        bar_count = self._bar_count_spin.value()
        htf_text = self._htf_edit.toPlainText().strip()

        # Try to build a KlineFrame snapshot
        frame = self._take_snapshot(symbol, timeframe, bar_count)
        if frame is None:
            self._status_bar.showMessage("数据不足，请等待缓冲区填满后再提交")
            return

        # Build orchestrator (if ctx has the necessary components)
        orchestrator = self._build_orchestrator()
        if orchestrator is None:
            self._status_bar.showMessage("编排器未就绪，请检查设置")
            return

        # Create cancel token
        from pa_agent.util.threading import CancelToken

        self._cancel_token = CancelToken()

        # Start worker in its own QThread (worker IS a QThread subclass)
        self._worker = _AnalysisWorker(
            orchestrator=orchestrator,
            frame=frame,
            htf_text=htf_text,
            cancel_token=self._cancel_token,
            parent=None,  # No parent so it can be moved/managed independently
        )
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.status_update.connect(self._on_status_update)
        self._worker.finished.connect(lambda _: self._on_worker_done())

        self._analysis_in_progress = True
        self._update_submit_button_state()
        self._status_bar.showMessage("分析中…")
        self._worker.start()

    def _on_analysis_finished(self, decision: dict) -> None:
        """Called on the main thread when the AI worker completes.

        *decision* is the full stage2 JSON dict (``{"decision": {...},
        "diagnosis_summary": {...}}``).  The chart and panel widgets expect
        the inner ``decision`` sub-dict, so we extract it here.
        """
        if decision:
            # The stage2 JSON has a nested "decision" key; extract it so that
            # ChartWidget and DecisionPanel receive the flat decision dict.
            inner = decision.get("decision", decision)
            self._chart_widget.set_decision(inner)
            self._decision_panel.set_decision(inner)
        else:
            self._decision_panel.clear()

    def _on_worker_done(self) -> None:
        """Reset in-progress flag and re-enable the submit button."""
        self._analysis_in_progress = False
        self._worker = None
        self._update_submit_button_state()
        self._status_bar.showMessage("分析完成")

    def _open_settings_dialog(self) -> None:
        """Open the SettingsDialog; import lazily to avoid circular imports."""
        from pa_agent.gui.settings_dialog import SettingsDialog
        from pa_agent.config.settings import Settings

        settings: Settings = self._ctx.settings  # type: ignore[assignment]
        if settings is None:
            settings = Settings()

        dlg = SettingsDialog(settings, parent=self)
        dlg.exec()
        self._ctx.settings = settings

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _can_submit(self) -> bool:
        """Return True if the submit button should be enabled."""
        if self._analysis_in_progress:
            return False
        if self._switching:
            return False
        exc_count = self._get_consecutive_count()
        if exc_count >= 2:
            return False
        return True

    def _update_submit_button_state(self) -> None:
        """Enable or disable the submit button based on current state."""
        self._submit_btn.setEnabled(self._can_submit())

    def _get_consecutive_count(self) -> int:
        """Return the current consecutive exception count (0 if unavailable)."""
        try:
            exc_counter = getattr(self._ctx, "exc_counter", None)
            if exc_counter is not None:
                return exc_counter.consecutive_count
        except Exception:  # noqa: BLE001
            pass
        return 0

    def _take_snapshot(self, symbol: str, timeframe: str, bar_count: int) -> Any:
        """Attempt to take a KlineFrame snapshot from the buffer.

        Returns None if the buffer is not ready.
        """
        try:
            buffer = getattr(self._ctx, "buffer", None)
            if buffer is None:
                return None
            from pa_agent.data.snapshot import take_snapshot

            return take_snapshot(buffer, bar_count, symbol, timeframe)
        except ValueError:
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Snapshot failed: %s", exc)
            return None

    def _build_orchestrator(self) -> Any:
        """Build a TwoStageOrchestrator from ctx components, or return None."""
        try:
            from pa_agent.orchestrator.two_stage import TwoStageOrchestrator

            client = getattr(self._ctx, "client", None)
            assembler = getattr(self._ctx, "assembler", None)
            router = getattr(self._ctx, "router", None)
            validator = getattr(self._ctx, "validator", None)
            exc_counter = getattr(self._ctx, "exc_counter", None)
            pending_writer = getattr(self._ctx, "pending_writer", None)
            exp_reader = getattr(self._ctx, "exp_reader", None)
            settings = getattr(self._ctx, "settings", None)

            if any(
                x is None
                for x in [client, assembler, router, validator, exc_counter,
                           pending_writer, exp_reader]
            ):
                return None

            return TwoStageOrchestrator(
                client=client,
                assembler=assembler,
                router=router,
                validator=validator,
                exc_counter=exc_counter,
                pending_writer=pending_writer,
                exp_reader=exp_reader,
                settings=settings,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not build orchestrator: %s", exc)
            return None
