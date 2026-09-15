"""Load local development environment variables without overriding the process."""
from __future__ import annotations

import logging
from pathlib import Path

from pa_agent.config.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)


def load_project_env(path: Path | None = None) -> bool:
    """Load the project .env while keeping explicitly exported variables authoritative."""
    env_path = path or PROJECT_ROOT / ".env"
    try:
        from dotenv import load_dotenv

        return bool(load_dotenv(dotenv_path=env_path, override=False))
    except ImportError:
        logger.debug("python-dotenv is not installed; skipping local .env file loading.")
        return False
