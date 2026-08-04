"""Load local development environment variables without overriding the process."""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from pa_agent.config.paths import PROJECT_ROOT


def load_project_env(path: Path | None = None) -> bool:
    """Load the project .env while keeping explicitly exported variables authoritative."""
    env_path = path or PROJECT_ROOT / ".env"
    return bool(load_dotenv(dotenv_path=env_path, override=False))
