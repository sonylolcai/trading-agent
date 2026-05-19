"""Pydantic settings models for PA Agent."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class PricingTable(BaseModel):
    """Per-million-token pricing in CNY (DeepSeek V4 Pro defaults)."""
    input_cache_hit: float = 0.1      # ¥/M tokens (cache hit)
    input_cache_miss: float = 12.0    # ¥/M tokens (cache miss)
    output: float = 24.0              # ¥/M tokens (output)


class AIProviderSettings(BaseModel):
    """AI provider connection and behaviour settings."""
    model: str = "deepseek-v4-pro"
    base_url: str = "https://api.deepseek.com"
    # api_key is the in-memory plaintext field; never serialised directly.
    api_key: str = ""
    # api_key_encrypted is the on-disk ciphertext field.
    api_key_encrypted: str = ""
    thinking: bool = True
    reasoning_effort: Literal["low", "medium", "high", "max"] = "max"
    context_window: int = 1_000_000
    pricing: PricingTable = Field(default_factory=PricingTable)


class GeneralSettings(BaseModel):
    """UI and data-feed general settings."""
    default_bar_count: int = 200
    refresh_interval_ms: int = 1000
    cost_warning_threshold_pct: float = 80.0
    last_symbol: str = "XAUUSD"
    last_timeframe: str = "1h"
    last_htf_text: str = ""


class Settings(BaseModel):
    """Root settings object persisted to config/settings.json."""
    provider: AIProviderSettings = Field(default_factory=AIProviderSettings)
    general: GeneralSettings = Field(default_factory=GeneralSettings)


# ── Persistence ───────────────────────────────────────────────────────────────
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_settings(path: Path | None = None) -> "Settings":
    """Load settings from *path* (default: SETTINGS_JSON_PATH).

    Decrypts api_key_encrypted → api_key in memory.
    Returns default Settings and writes them to disk if the file is absent.
    """
    from pa_agent.config.paths import SETTINGS_JSON_PATH
    from pa_agent.security.secret_store import SecretStore

    path = path or SETTINGS_JSON_PATH

    if not path.exists():
        defaults = Settings()
        save_settings(defaults, path)
        return defaults

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("settings.json unreadable (%s); using defaults", exc)
        return Settings()

    # Decrypt api_key back into memory field
    encrypted = raw.get("provider", {}).get("api_key_encrypted", "")
    if encrypted:
        try:
            raw.setdefault("provider", {})["api_key"] = SecretStore.decrypt(encrypted)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to decrypt api_key (%s); leaving blank", exc)
            raw.setdefault("provider", {})["api_key"] = ""

    return Settings.model_validate(raw)


def save_settings(settings: "Settings", path: Path | None = None) -> None:
    """Persist settings to *path* (default: SETTINGS_JSON_PATH).

    Encrypts api_key → api_key_encrypted; never writes plaintext api_key.
    """
    from pa_agent.config.paths import SETTINGS_JSON_PATH
    from pa_agent.security.secret_store import SecretStore

    path = path or SETTINGS_JSON_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    data = settings.model_dump()

    # Encrypt and strip plaintext key
    plaintext = data.get("provider", {}).get("api_key", "")
    if plaintext:
        data["provider"]["api_key_encrypted"] = SecretStore.encrypt(plaintext)
    data["provider"].pop("api_key", None)  # never write plaintext

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
