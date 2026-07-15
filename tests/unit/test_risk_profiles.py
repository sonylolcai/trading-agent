from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from pa_agent.api.app import create_app
from pa_agent.api.context import ApiContext
from pa_agent.config.settings import Settings
from pa_agent.data.kline_cache import KlineCacheStore


def _context(tmp_path: Path) -> ApiContext:
    return ApiContext(
        settings=Settings(),
        kline_cache=KlineCacheStore(tmp_path / "cache"),
        records_dir=tmp_path / "records",
    )


def test_apply_risk_profile_sets_stance_and_signal_threshold() -> None:
    from pa_agent.ai.decision_stance import RISK_PROFILE_PRESETS, apply_risk_profile

    settings = Settings()

    apply_risk_profile(settings.general, "aggressive")

    assert settings.general.decision_stance == "aggressive"
    assert (
        settings.general.decision_confidence_threshold
        == RISK_PROFILE_PRESETS["aggressive"].signal_threshold
    )


def test_risk_profile_route_updates_settings_and_returns_payload(tmp_path: Path) -> None:
    context = _context(tmp_path)
    client = TestClient(create_app(context))

    response = client.patch(
        "/api/settings/risk-profile",
        json={"risk_profile": "conservative"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["general"]["decision_stance"] == "conservative"
    assert payload["general"]["decision_confidence_threshold"] == 60
    assert context.settings.general.decision_stance == "conservative"
    assert context.settings.general.decision_confidence_threshold == 60


def test_risk_profile_route_rejects_unknown_profile(tmp_path: Path) -> None:
    client = TestClient(create_app(_context(tmp_path)))

    response = client.patch(
        "/api/settings/risk-profile",
        json={"risk_profile": "reckless"},
    )

    assert response.status_code == 422
