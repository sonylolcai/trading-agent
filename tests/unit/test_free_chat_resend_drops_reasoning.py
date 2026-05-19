"""Tests for FreeChatSession: default behaviour drops reasoning_content from
history_for_api but preserves it in history_full.

Task 12.4 — Validates: Requirements R11.4, R11.5
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch
import pytest

from pa_agent.orchestrator.free_chat import FreeChatSession
from pa_agent.records.schema import AnalysisRecord, RecordMeta
from pa_agent.util.threading import CancelToken


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reply(content: str = "AI response", reasoning: str = "AI reasoning") -> MagicMock:
    """Build a mock AIReply."""
    reply = MagicMock()
    reply.content = content
    reply.reasoning_content = reasoning
    reply.raw = {}
    reply.usage = MagicMock()
    reply.usage.prompt_tokens = 100
    reply.usage.completion_tokens = 50
    reply.usage.cached_prompt_tokens = 0
    reply.usage.total_tokens = 150
    return reply


def _make_base_record() -> AnalysisRecord:
    """Build a minimal AnalysisRecord for testing."""
    meta = RecordMeta(
        timestamp_local_iso="2026-05-18T14:00:13.000",
        timestamp_local_ms=1_747_569_613_000,
        symbol="XAUUSD",
        timeframe="1h",
        bar_count=2,
        ai_provider={"model": "deepseek-v4-pro"},
    )
    return AnalysisRecord(
        meta=meta,
        kline_data=[],
        htf_text="",
        stage1_messages=[],
        stage1_response=None,
        stage1_diagnosis=None,
        stage2_messages=[
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user msg"},
        ],
        stage2_response={
            "content": "stage2 content",
            "reasoning_content": "stage2 reasoning",
        },
        stage2_decision={"decision": {"order_type": "不下单"}},
        strategy_files_used=[],
        experience_loaded=[],
        exception=None,
        usage_total={},
    )


def _make_session(client: MagicMock) -> FreeChatSession:
    """Build a FreeChatSession with mock dependencies."""
    assembler = MagicMock()
    pending_writer = MagicMock()
    ledger = MagicMock()
    base_record = _make_base_record()
    session = FreeChatSession(
        base_record=base_record,
        client=client,
        assembler=assembler,
        pending_writer=pending_writer,
        ledger=ledger,
    )
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFreeChatResendDropsReasoning:
    """Default keep_reasoning_in_resend=False: reasoning stripped from API calls."""

    def test_default_flag_is_false(self):
        client = MagicMock()
        session = _make_session(client)
        assert session.keep_reasoning_in_resend is False

    def test_three_turns_history_for_api_has_no_reasoning_content(self):
        """After 3 sends, every assistant message in history_for_api must lack
        reasoning_content."""
        client = MagicMock()
        client.chat.side_effect = [
            _make_reply("reply 1", "reasoning 1"),
            _make_reply("reply 2", "reasoning 2"),
            _make_reply("reply 3", "reasoning 3"),
        ]
        session = _make_session(client)
        cancel = CancelToken()

        session.send("question 1", cancel)
        session.send("question 2", cancel)
        session.send("question 3", cancel)

        assert client.chat.call_count == 3

        # Inspect every call's history_for_api (first positional arg)
        for call_args in client.chat.call_args_list:
            messages: list[dict] = call_args[0][0]
            for msg in messages:
                if msg.get("role") == "assistant":
                    assert "reasoning_content" not in msg, (
                        f"reasoning_content found in assistant message: {msg}"
                    )

    def test_history_full_preserves_reasoning_content(self):
        """history_full must retain reasoning_content for all assistant turns."""
        client = MagicMock()
        client.chat.side_effect = [
            _make_reply("reply 1", "reasoning 1"),
            _make_reply("reply 2", "reasoning 2"),
            _make_reply("reply 3", "reasoning 3"),
        ]
        session = _make_session(client)
        cancel = CancelToken()

        session.send("question 1", cancel)
        session.send("question 2", cancel)
        session.send("question 3", cancel)

        assistant_msgs = [
            m for m in session.history_full if m.get("role") == "assistant"
        ]
        assert len(assistant_msgs) == 3
        for i, msg in enumerate(assistant_msgs, start=1):
            assert "reasoning_content" in msg, (
                f"Turn {i} assistant message missing reasoning_content"
            )
            assert msg["reasoning_content"] == f"reasoning {i}"

    def test_stage2_assistant_reasoning_stripped_from_api(self):
        """The stage2 assistant message in history_for_api must not carry
        reasoning_content (it comes from base_record.stage2_response)."""
        client = MagicMock()
        client.chat.return_value = _make_reply()
        session = _make_session(client)
        cancel = CancelToken()

        session.send("hello", cancel)

        messages: list[dict] = client.chat.call_args[0][0]
        # Find the stage2 assistant message (third message: system, user, assistant)
        assert len(messages) >= 3
        stage2_assistant = messages[2]
        assert stage2_assistant["role"] == "assistant"
        assert stage2_assistant["content"] == "stage2 content"
        assert "reasoning_content" not in stage2_assistant

    def test_turn_counter_increments(self):
        """Each send increments the internal turn counter."""
        client = MagicMock()
        client.chat.return_value = _make_reply()
        pending_writer = MagicMock()
        session = FreeChatSession(
            base_record=_make_base_record(),
            client=client,
            assembler=MagicMock(),
            pending_writer=pending_writer,
            ledger=MagicMock(),
        )
        cancel = CancelToken()

        session.send("msg 1", cancel)
        session.send("msg 2", cancel)
        session.send("msg 3", cancel)

        # Check that append_followup was called with turn numbers 1, 2, 3
        calls = pending_writer.append_followup.call_args_list
        assert len(calls) == 3
        for i, c in enumerate(calls, start=1):
            turn_obj = c[0][1]  # second positional arg is the FollowupTurn
            assert turn_obj.turn == i

    def test_ledger_add_called_per_send(self):
        """ledger.add must be called once per successful send."""
        client = MagicMock()
        client.chat.return_value = _make_reply()
        ledger = MagicMock()
        session = FreeChatSession(
            base_record=_make_base_record(),
            client=client,
            assembler=MagicMock(),
            pending_writer=MagicMock(),
            ledger=ledger,
        )
        cancel = CancelToken()

        session.send("msg 1", cancel)
        session.send("msg 2", cancel)

        assert ledger.add.call_count == 2

    def test_history_for_api_structure_first_turn(self):
        """On the first send, history_for_api should be:
        [system, stage2_user, stage2_assistant, new_user]."""
        client = MagicMock()
        client.chat.return_value = _make_reply()
        session = _make_session(client)
        cancel = CancelToken()

        session.send("my question", cancel)

        messages: list[dict] = client.chat.call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "system prompt"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "user msg"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "stage2 content"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "my question"

    def test_history_for_api_grows_with_turns(self):
        """On the second send, previous free-chat turn is included in
        history_for_api (without reasoning_content)."""
        client = MagicMock()
        client.chat.side_effect = [
            _make_reply("reply 1", "reasoning 1"),
            _make_reply("reply 2", "reasoning 2"),
        ]
        session = _make_session(client)
        cancel = CancelToken()

        session.send("question 1", cancel)
        session.send("question 2", cancel)

        # Second call's messages
        messages: list[dict] = client.chat.call_args_list[1][0][0]
        # system, stage2_user, stage2_assistant, q1, a1, q2
        assert len(messages) == 6
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "question 1"
        assert messages[4]["role"] == "assistant"
        assert messages[4]["content"] == "reply 1"
        assert "reasoning_content" not in messages[4]
        assert messages[5]["role"] == "user"
        assert messages[5]["content"] == "question 2"
