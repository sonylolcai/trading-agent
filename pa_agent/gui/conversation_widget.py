"""ConversationWidget — Tab 2 conversation panel.

Displays stage1/stage2 reasoning and content, a free-chat message stream,
an input area, and a real-time token/cost indicator.

Design reference: design.md §B.11 (Tab2), §B.9 (token/cost)
Tasks: 15.1, 15.2, 15.3, 15.4
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pa_agent.orchestrator.free_chat import FreeChatSession
    from pa_agent.util.threading import CancelToken

logger = logging.getLogger(__name__)

# ── Colour thresholds ─────────────────────────────────────────────────────────
_YELLOW_PCT = 80.0
_RED_PCT = 95.0

_STYLE_NORMAL = ""
_STYLE_YELLOW = "QProgressBar::chunk { background-color: #e6b800; }"
_STYLE_RED = "QProgressBar::chunk { background-color: #cc0000; }"


# ── Worker for FreeChatSession.send ──────────────────────────────────────────

class _ChatWorker(QThread):
    """Runs FreeChatSession.send() on a background thread.

    Signals
    -------
    finished(str, str):
        Emitted with (content, reasoning_content) on success.
    error(str):
        Emitted with an error message on failure.
    """

    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(
        self,
        session: "FreeChatSession",
        user_text: str,
        cancel_token: "CancelToken",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._user_text = user_text
        self._cancel_token = cancel_token

    def run(self) -> None:
        try:
            reply = self._session.send(self._user_text, self._cancel_token)
            self.finished.emit(reply.content, reply.reasoning_content or "")
        except Exception as exc:  # noqa: BLE001
            logger.error("ChatWorker error: %s", exc, exc_info=True)
            self.error.emit(str(exc))


# ── Collapsible reasoning block ───────────────────────────────────────────────

class _ReasoningBlock(QWidget):
    """A collapsible block that shows reasoning_content inside a QGroupBox."""

    def __init__(self, title: str, reasoning: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Toggle button
        self._toggle_btn = QToolButton()
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(False)  # collapsed by default
        self._toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self._toggle_btn.setText(f"{title} (推理过程 — 点击展开)")
        self._toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self._toggle_btn)

        # Content area (hidden by default)
        self._content = QTextEdit()
        self._content.setReadOnly(True)
        self._content.setPlainText(reasoning)
        self._content.setStyleSheet("background-color: #f5f5f5; color: #555555;")
        self._content.setMaximumHeight(200)
        self._content.setVisible(False)
        layout.addWidget(self._content)

    def _on_toggle(self, checked: bool) -> None:
        self._content.setVisible(checked)
        self._toggle_btn.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
        if checked:
            self._toggle_btn.setText(
                self._toggle_btn.text().replace("展开", "折叠")
            )
        else:
            self._toggle_btn.setText(
                self._toggle_btn.text().replace("折叠", "展开")
            )


# ── Stage result block ────────────────────────────────────────────────────────

class _StageResultBlock(QWidget):
    """Displays a single stage result: optional reasoning (collapsed) + content."""

    def __init__(
        self,
        stage_label: str,
        content: str,
        reasoning: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Stage header
        header = QLabel(f"<b>{stage_label}</b>")
        layout.addWidget(header)

        # Reasoning (collapsible)
        if reasoning:
            reasoning_block = _ReasoningBlock(stage_label, reasoning)
            layout.addWidget(reasoning_block)

        # Content
        content_edit = QTextEdit()
        content_edit.setReadOnly(True)
        content_edit.setPlainText(content)
        content_edit.setMaximumHeight(150)
        layout.addWidget(content_edit)


# ── Message bubble ────────────────────────────────────────────────────────────

class _MessageBubble(QWidget):
    """A single chat message bubble with optional collapsible reasoning."""

    def __init__(
        self,
        role: str,
        content: str,
        reasoning: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        # Role label
        role_label = QLabel(f"<b>{'用户' if role == 'user' else 'AI'}</b>")
        if role == "user":
            role_label.setStyleSheet("color: #0066cc;")
        else:
            role_label.setStyleSheet("color: #006600;")
        layout.addWidget(role_label)

        # Reasoning (collapsible, AI only)
        if reasoning and role == "assistant":
            reasoning_block = _ReasoningBlock("AI 推理", reasoning)
            layout.addWidget(reasoning_block)

        # Content
        content_edit = QTextEdit()
        content_edit.setReadOnly(True)
        content_edit.setPlainText(content)
        content_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        # Auto-resize height based on content
        doc = content_edit.document()
        doc.setTextWidth(content_edit.viewport().width())
        height = min(300, max(60, int(doc.size().height()) + 20))
        content_edit.setMaximumHeight(height)
        layout.addWidget(content_edit)


# ── ConversationWidget ────────────────────────────────────────────────────────

class ConversationWidget(QWidget):
    """Tab 2 widget: stage results + free-chat stream + token indicator.

    State machine
    -------------
    - Input disabled by default.
    - ``on_record_saved()`` enables input (two-stage analysis succeeded).
    - ``on_analysis_started()`` disables input and clears the FreeChatSession.

    Public API
    ----------
    show_stage_result(stage, content, reasoning)
    append_message(role, content, reasoning)
    set_input_enabled(enabled)
    update_token_display(data)
    clear()
    on_record_saved()
    on_analysis_started()
    set_session(session)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: Optional["FreeChatSession"] = None
        self._cancel_token: Optional["CancelToken"] = None
        self._worker: Optional[_ChatWorker] = None
        self._sending = False
        self._red_warned = False  # one-time 95% warning flag

        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ── Token / cost indicator ────────────────────────────────────────────
        outer.addWidget(self._build_token_indicator())

        # ── Message stream (scrollable) ───────────────────────────────────────
        self._stream_container = QWidget()
        self._stream_layout = QVBoxLayout(self._stream_container)
        self._stream_layout.setContentsMargins(0, 0, 0, 0)
        self._stream_layout.setSpacing(4)
        self._stream_layout.addStretch()  # push messages to top

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._stream_container)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        outer.addWidget(scroll, stretch=1)
        self._scroll_area = scroll

        # ── Input area ────────────────────────────────────────────────────────
        outer.addWidget(self._build_input_area())

        # Start disabled
        self.set_input_enabled(False)

    def _build_token_indicator(self) -> QWidget:
        """Build the token/cost indicator section."""
        group = QGroupBox("Token 用量与费用")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("0 / 0  (0.0%)")
        layout.addWidget(self._progress_bar)

        # Token count label
        self._token_label = QLabel("Tokens: 0 prompt + 0 completion = 0 total")
        layout.addWidget(self._token_label)

        # Cost breakdown labels
        cost_row = QHBoxLayout()
        self._cost_cache_hit_label = QLabel("缓存命中: ¥0.000000")
        self._cost_cache_miss_label = QLabel("缓存未命中: ¥0.000000")
        self._cost_output_label = QLabel("输出: ¥0.000000")
        self._cost_total_label = QLabel("合计: ¥0.000000")
        for lbl in (
            self._cost_cache_hit_label,
            self._cost_cache_miss_label,
            self._cost_output_label,
            self._cost_total_label,
        ):
            cost_row.addWidget(lbl)
        cost_row.addStretch()
        layout.addLayout(cost_row)

        return group

    def _build_input_area(self) -> QWidget:
        """Build the input area: QPlainTextEdit + send/stop button."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._input_edit = QPlainTextEdit()
        self._input_edit.setPlaceholderText("输入消息后按发送…")
        self._input_edit.setMaximumHeight(80)
        layout.addWidget(self._input_edit, stretch=1)

        self._send_btn = QPushButton("发送")
        self._send_btn.setMinimumWidth(70)
        self._send_btn.clicked.connect(self._on_send_or_stop)
        layout.addWidget(self._send_btn)

        return container

    # ── Public API ────────────────────────────────────────────────────────────

    def show_stage_result(self, stage: str, content: str, reasoning: str) -> None:
        """Add a stage1 or stage2 result block to the message stream."""
        block = _StageResultBlock(stage, content, reasoning)
        # Insert before the trailing stretch
        count = self._stream_layout.count()
        self._stream_layout.insertWidget(count - 1, block)
        self._scroll_to_bottom()

    def append_message(self, role: str, content: str, reasoning: str = "") -> None:
        """Add a free-chat message bubble to the stream."""
        bubble = _MessageBubble(role, content, reasoning)
        count = self._stream_layout.count()
        self._stream_layout.insertWidget(count - 1, bubble)
        self._scroll_to_bottom()

    def set_input_enabled(self, enabled: bool) -> None:
        """Enable or disable the input area."""
        self._input_edit.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

    def update_token_display(self, data: dict) -> None:
        """Refresh the token/cost indicator.

        Expected keys in *data*:
            context_used, context_window,
            total_input, total_cached_input, total_output, total_cny
        """
        context_used = data.get("context_used", 0)
        context_window = data.get("context_window", 1_000_000)
        total_input = data.get("total_input", 0)
        total_cached_input = data.get("total_cached_input", 0)
        total_output = data.get("total_output", 0)
        total_cny = data.get("total_cny", 0.0)

        # Percentage
        pct = (context_used / context_window * 100.0) if context_window > 0 else 0.0
        pct_int = min(100, int(pct))

        # Progress bar
        self._progress_bar.setValue(pct_int)
        self._progress_bar.setFormat(
            f"{context_used:,} / {context_window:,}  ({pct:.1f}%)"
        )

        # Colour thresholds
        if pct >= _RED_PCT:
            self._progress_bar.setStyleSheet(_STYLE_RED)
            if not self._red_warned:
                self._red_warned = True
                QMessageBox.warning(
                    self,
                    "上下文用量警告",
                    f"上下文用量已达 {pct:.1f}%，接近 1M 上限，建议开启新会话。",
                )
        elif pct >= _YELLOW_PCT:
            self._progress_bar.setStyleSheet(_STYLE_YELLOW)
        else:
            self._progress_bar.setStyleSheet(_STYLE_NORMAL)

        # Token label
        total_tokens = total_input + total_output
        self._token_label.setText(
            f"Tokens: {total_input:,} prompt + {total_output:,} completion"
            f" = {total_tokens:,} total  ({pct:.1f}%)"
        )

        # Cost breakdown — derive from totals using pricing if available
        # We display total_cny directly; individual breakdown requires pricing
        # which is not passed here. Show total only.
        self._cost_total_label.setText(f"合计: ¥{total_cny:.6f}")

        # Try to get breakdown from session ledger if available
        # (individual labels updated separately via _update_cost_breakdown)

    def clear(self) -> None:
        """Clear all messages from the stream."""
        # Remove all widgets except the trailing stretch
        while self._stream_layout.count() > 1:
            item = self._stream_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._red_warned = False
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("0 / 0  (0.0%)")
        self._progress_bar.setStyleSheet(_STYLE_NORMAL)
        self._token_label.setText("Tokens: 0 prompt + 0 completion = 0 total")
        self._cost_total_label.setText("合计: ¥0.000000")

    # ── State machine slots ───────────────────────────────────────────────────

    def on_record_saved(self) -> None:
        """Slot: two-stage analysis succeeded — enable input."""
        self.set_input_enabled(True)

    def on_analysis_started(self) -> None:
        """Slot: new analysis started — disable input and clear FreeChatSession."""
        self.set_input_enabled(False)
        self._session = None
        self._cancel_token = None

    # ── Session wiring ────────────────────────────────────────────────────────

    def set_session(
        self,
        session: "FreeChatSession",
        cancel_token: "CancelToken",
    ) -> None:
        """Wire a FreeChatSession and its CancelToken to this widget."""
        self._session = session
        self._cancel_token = cancel_token

    # ── Send / stop ───────────────────────────────────────────────────────────

    def _on_send_or_stop(self) -> None:
        if self._sending:
            self._on_stop()
        else:
            self._on_send()

    def _on_send(self) -> None:
        if self._session is None:
            return
        text = self._input_edit.toPlainText().strip()
        if not text:
            return

        # Reset cancel token for this turn
        from pa_agent.util.threading import CancelToken

        self._cancel_token = CancelToken()

        # Show user message immediately
        self.append_message("user", text)
        self._input_edit.clear()

        # Switch button to "停止"
        self._sending = True
        self._send_btn.setText("停止")
        self._input_edit.setEnabled(False)

        # Start worker
        self._worker = _ChatWorker(self._session, text, self._cancel_token, parent=self)
        self._worker.finished.connect(self._on_reply_received)
        self._worker.error.connect(self._on_reply_error)
        self._worker.finished.connect(lambda *_: self._on_worker_done())
        self._worker.error.connect(lambda *_: self._on_worker_done())
        self._worker.start()

    def _on_stop(self) -> None:
        if self._cancel_token is not None:
            self._cancel_token.set()

    def _on_reply_received(self, content: str, reasoning: str) -> None:
        self.append_message("assistant", content, reasoning)
        # Refresh token display via session ledger if available
        if self._session is not None:
            ledger = getattr(self._session, "_ledger", None)
            if ledger is not None:
                self.update_token_display(ledger.breakdown())

    def _on_reply_error(self, error_msg: str) -> None:
        self.append_message("assistant", f"[错误] {error_msg}")

    def _on_worker_done(self) -> None:
        self._sending = False
        self._send_btn.setText("发送")
        self._input_edit.setEnabled(True)
        self._worker = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _scroll_to_bottom(self) -> None:
        """Scroll the message stream to the bottom."""
        sb = self._scroll_area.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())
