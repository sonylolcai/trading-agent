"""Runtime context for the local Web API."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pa_agent.api.analysis_service import (
    AnalysisRunner,
    AnalysisTaskStore,
    default_analysis_runner,
)
from pa_agent.backtest.record_replay import rebuild_setup_stats_from_records
from pa_agent.config.paths import RECORDS_PENDING_DIR, SETTINGS_JSON_PATH, SETUP_STATS_JSON_PATH
from pa_agent.config.settings import Settings, load_settings
from pa_agent.data.kline_cache import KlineCacheStore


@dataclass(slots=True)
class ApiContext:
    """Small API-only context that avoids bootstrapping GUI, AI, or live data."""

    settings: Settings
    kline_cache: KlineCacheStore = field(default_factory=KlineCacheStore)
    records_dir: Path = RECORDS_PENDING_DIR
    setup_stats_path: Path = SETUP_STATS_JSON_PATH
    analysis_tasks: AnalysisTaskStore = field(default_factory=AnalysisTaskStore)
    analysis_runner: AnalysisRunner = default_analysis_runner
    rebuild_setup_stats: Callable[..., object] = rebuild_setup_stats_from_records

    @classmethod
    def load(cls) -> "ApiContext":
        return cls(settings=load_settings(SETTINGS_JSON_PATH))
