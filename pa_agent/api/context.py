"""Runtime context for the local Web API."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pa_agent.config.paths import RECORDS_PENDING_DIR, SETTINGS_JSON_PATH
from pa_agent.config.settings import Settings, load_settings
from pa_agent.data.kline_cache import KlineCacheStore


@dataclass(slots=True)
class ApiContext:
    """Small API-only context that avoids bootstrapping GUI, AI, or live data."""

    settings: Settings
    kline_cache: KlineCacheStore = field(default_factory=KlineCacheStore)
    records_dir: Path = RECORDS_PENDING_DIR

    @classmethod
    def load(cls) -> "ApiContext":
        return cls(settings=load_settings(SETTINGS_JSON_PATH))
