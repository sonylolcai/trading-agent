"""DeepSeek AI client (OpenAI-compatible API)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pa_agent.util.threading import CancelToken

from pa_agent.config.settings import AIProviderSettings
from pa_agent.security.secret_store import mask_secret

logger = logging.getLogger(__name__)


@dataclass
class AIUsage:
    """Token usage from a single API call."""
    prompt_tokens: int = 0
    cached_prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AIReply:
    """Structured response from a single AI API call."""
    content: str
    reasoning_content: str
    raw: dict[str, Any]          # full raw response dict for debug tab
    usage: AIUsage
    request_id: str
    latency_ms: float


class CancelledError(Exception):
    """Raised when a cancel_token is set before or during an API call."""


class DeepSeekClient:
    """Thin wrapper around the OpenAI-compatible DeepSeek API."""

    def __init__(self, settings: AIProviderSettings, logger_: logging.Logger | None = None) -> None:
        self._settings = settings
        self._log = logger_ or logger

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        thinking: bool | None = None,
        reasoning_effort: str | None = None,
        context_window: int | None = None,
        cancel_token: "CancelToken | None" = None,
        timeout_s: float = 600.0,
    ) -> AIReply:
        """Send *messages* to the DeepSeek API and return a structured reply.

        Raises CancelledError if cancel_token is set before the call.
        Never sends temperature/top_p/presence_penalty/frequency_penalty.
        """
        # Check cancellation before making the network call
        if cancel_token is not None and cancel_token.is_set():
            raise CancelledError("Request cancelled before API call")

        # Resolve settings
        _thinking = thinking if thinking is not None else self._settings.thinking
        _effort = reasoning_effort if reasoning_effort is not None else self._settings.reasoning_effort

        # Build extra_body — this is the ONLY way to pass thinking params
        extra_body: dict[str, Any] = {
            "thinking": {"type": "enabled" if _thinking else "disabled"},
            "reasoning_effort": _effort,
        }

        masked_key = mask_secret(self._settings.api_key)
        self._log.debug(
            "DeepSeekClient.chat: model=%s thinking=%s effort=%s key=...%s msgs=%d",
            self._settings.model, _thinking, _effort, masked_key[-4:] if len(masked_key) >= 4 else "****",
            len(messages),
        )

        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc

        client = OpenAI(
            base_url=self._settings.base_url,
            api_key=self._settings.api_key,
        )

        t0 = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=self._settings.model,
                messages=messages,
                extra_body=extra_body,
                timeout=timeout_s,
                # IMPORTANT: do NOT add temperature, top_p, presence_penalty,
                # frequency_penalty — they are incompatible with thinking mode.
            )
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            self._log.error("DeepSeekClient API error after %.0f ms: %s", latency_ms, exc)
            raise

        latency_ms = (time.monotonic() - t0) * 1000

        msg = response.choices[0].message
        content = msg.content or ""
        reasoning_content = getattr(msg, "reasoning_content", None) or ""

        # Build usage
        u = response.usage
        usage = AIUsage(
            prompt_tokens=getattr(u, "prompt_tokens", 0),
            cached_prompt_tokens=getattr(
                getattr(u, "prompt_tokens_details", None), "cached_tokens", 0
            ) if u else 0,
            completion_tokens=getattr(u, "completion_tokens", 0),
            total_tokens=getattr(u, "total_tokens", 0),
        )

        request_id = getattr(response, "id", "") or ""

        # Build raw dict for debug tab — mask API key if it somehow appears
        raw: dict[str, Any] = {
            "id": request_id,
            "model": getattr(response, "model", ""),
            "content": content,
            "reasoning_content": reasoning_content,
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "cached_prompt_tokens": usage.cached_prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            },
            "latency_ms": latency_ms,
        }

        self._log.debug(
            "DeepSeekClient.chat done: latency=%.0f ms tokens=%d/%d",
            latency_ms, usage.prompt_tokens, usage.completion_tokens,
        )

        return AIReply(
            content=content,
            reasoning_content=reasoning_content,
            raw=raw,
            usage=usage,
            request_id=request_id,
            latency_ms=latency_ms,
        )
