"""Unit tests for DeepSeekClient (task 6.5)."""
from __future__ import annotations

import sys
import pytest
from unittest.mock import MagicMock, patch, call
from pa_agent.config.settings import AIProviderSettings
from pa_agent.ai.deepseek_client import DeepSeekClient, AIReply, AIUsage, CancelledError


def _make_settings(api_key: str = "sk-test-1234abcd") -> AIProviderSettings:
    s = AIProviderSettings()
    s.api_key = api_key
    return s


def _make_mock_response(content: str = "hello", reasoning: str = "thinking...") -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.reasoning_content = reasoning
    choice = MagicMock()
    choice.message = msg
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    usage.total_tokens = 150
    usage.prompt_tokens_details = MagicMock()
    usage.prompt_tokens_details.cached_tokens = 20
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp.id = "req-abc123"
    resp.model = "deepseek-v4-pro"
    return resp


def test_chat_does_not_send_forbidden_params():
    """chat() must never pass temperature/top_p/presence_penalty/frequency_penalty."""
    settings = _make_settings()
    client = DeepSeekClient(settings)

    mock_resp = _make_mock_response()
    mock_openai = MagicMock()
    mock_openai.return_value.chat.completions.create.return_value = mock_resp

    with patch("pa_agent.ai.deepseek_client.OpenAI", mock_openai):
        reply = client.chat([{"role": "user", "content": "hi"}])

    call_kwargs = mock_openai.return_value.chat.completions.create.call_args
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
    all_kwargs = {**(call_kwargs.args[0] if call_kwargs.args else {}), **kwargs}

    for forbidden in ("temperature", "top_p", "presence_penalty", "frequency_penalty"):
        assert forbidden not in all_kwargs, f"Forbidden param '{forbidden}' was sent to API"


def test_chat_extra_body_thinking_enabled():
    """extra_body must contain thinking.type=enabled and reasoning_effort."""
    settings = _make_settings()
    settings.thinking = True
    settings.reasoning_effort = "max"
    client = DeepSeekClient(settings)

    mock_resp = _make_mock_response()
    mock_openai = MagicMock()
    mock_openai.return_value.chat.completions.create.return_value = mock_resp

    with patch("pa_agent.ai.deepseek_client.OpenAI", mock_openai):
        client.chat([{"role": "user", "content": "hi"}])

    call_kwargs = mock_openai.return_value.chat.completions.create.call_args
    extra_body = call_kwargs.kwargs.get("extra_body", {})
    assert extra_body["thinking"]["type"] == "enabled"
    assert extra_body["reasoning_effort"] == "max"


def test_chat_cancel_token_raises():
    """If cancel_token is set, chat() raises CancelledError before calling API."""
    from pa_agent.util.threading import CancelToken
    settings = _make_settings()
    client = DeepSeekClient(settings)

    token = CancelToken()
    token.set()

    mock_openai = MagicMock()
    with patch("pa_agent.ai.deepseek_client.OpenAI", mock_openai):
        with pytest.raises(CancelledError):
            client.chat([{"role": "user", "content": "hi"}], cancel_token=token)

    # API must NOT have been called
    mock_openai.return_value.chat.completions.create.assert_not_called()


def test_chat_no_plaintext_key_in_logs(caplog):
    """API key must not appear in log output."""
    import logging
    settings = _make_settings(api_key="sk-super-secret-9999")
    client = DeepSeekClient(settings)

    mock_resp = _make_mock_response()
    mock_openai = MagicMock()
    mock_openai.return_value.chat.completions.create.return_value = mock_resp

    with caplog.at_level(logging.DEBUG, logger="pa_agent.ai.deepseek_client"):
        with patch("pa_agent.ai.deepseek_client.OpenAI", mock_openai):
            client.chat([{"role": "user", "content": "hi"}])

    for record in caplog.records:
        assert "sk-super-secret-9999" not in record.getMessage(), (
            f"Plaintext API key found in log: {record.getMessage()}"
        )


def test_chat_returns_aireply_fields():
    """chat() returns an AIReply with all expected fields populated."""
    settings = _make_settings()
    client = DeepSeekClient(settings)

    mock_resp = _make_mock_response(content="answer", reasoning="thought")
    mock_openai = MagicMock()
    mock_openai.return_value.chat.completions.create.return_value = mock_resp

    with patch("pa_agent.ai.deepseek_client.OpenAI", mock_openai):
        reply = client.chat([{"role": "user", "content": "hi"}])

    assert isinstance(reply, AIReply)
    assert reply.content == "answer"
    assert reply.reasoning_content == "thought"
    assert reply.usage.prompt_tokens == 100
    assert reply.usage.completion_tokens == 50
    assert reply.request_id == "req-abc123"
    assert reply.latency_ms >= 0
