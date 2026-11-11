"""PiP detection must say so once when the ATEM library has no PiP state."""
from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

from PyQt5.QtWidgets import QApplication

if not QApplication.instance():
    _app = QApplication(sys.argv)

from adapters.atem_monitor import ATEMMonitor


def test_missing_pip_state_warns_once_and_marks_unsupported(caplog):
    monitor = ATEMMonitor("192.0.2.1")
    emitted = []
    monitor.pip_changed.connect(emitted.append)
    atem = SimpleNamespace()  # no pictureInPicture attribute, like PyATEMMax 1.0b9
    with caplog.at_level(logging.WARNING, logger="adapters.atem_monitor"):
        for _ in range(50):
            monitor._poll_pip(atem)
    warns = [r for r in caplog.records if "pictureInPicture" in r.getMessage()]
    assert len(warns) == 1
    assert monitor.pip_supported is False
    assert emitted == []


def test_supported_pip_still_emits():
    monitor = ATEMMonitor("192.0.2.1")
    got = []
    monitor.pip_changed.connect(got.append)
    atem = SimpleNamespace(pictureInPicture=[SimpleNamespace(enabled=False, source=None)])
    monitor._poll_pip(atem)
    atem.pictureInPicture[0].enabled = True
    atem.pictureInPicture[0].source = 2
    monitor._poll_pip(atem)
    assert monitor.pip_supported is True
    assert len(got) == 1 and got[0].enabled is True
