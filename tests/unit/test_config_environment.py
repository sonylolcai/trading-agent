from __future__ import annotations

import builtins
from pathlib import Path
import pytest

from pa_agent.config.environment import load_project_env


def test_load_project_env_with_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_KEY_ENV=hello_world\n", encoding="utf-8")
    monkeypatch.delenv("TEST_KEY_ENV", raising=False)

    loaded = load_project_env(env_file)
    assert loaded is True


def test_load_project_env_graceful_on_import_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def mock_import(name: str, *args, **kwargs):
        if name == "dotenv":
            raise ImportError("No module named 'dotenv'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    assert load_project_env(tmp_path / ".env") is False