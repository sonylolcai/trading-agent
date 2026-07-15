from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from pa_agent.config.settings import Settings
from pa_agent.gui.general_settings_dialog import GeneralSettingsDialog
from pa_agent.gui.settings_dialog import SettingsDialog


def test_general_settings_dialog_profile_change_syncs_signal_threshold(qtbot) -> None:
    settings = Settings()
    dialog = GeneralSettingsDialog(settings)
    qtbot.addWidget(dialog)

    index = dialog._decision_stance_combo.findData("aggressive")
    dialog._decision_stance_combo.setCurrentIndex(index)

    assert dialog._decision_conf_threshold_spin.value() == 30


def test_settings_dialog_profile_change_syncs_signal_threshold(qtbot) -> None:
    settings = Settings()
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)

    index = dialog._decision_stance_combo.findData("conservative")
    dialog._decision_stance_combo.setCurrentIndex(index)

    assert dialog._decision_conf_threshold_spin.value() == 60
