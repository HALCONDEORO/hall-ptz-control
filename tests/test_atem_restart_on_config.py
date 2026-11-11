"""Changing or first-setting the ATEM IP at runtime must (re)start the monitor.

Two holes made the running ATEMMonitor keep polling the old address (or
never start at all) after runtime configuration:

1. ``_stop_and_replace_atem_monitor`` returned early when
   ``self._atem_monitor is None``, so the "Scan" and "Reconnect ATEM"
   buttons (which funnel through ``_do_restart_atem_monitor``) could never
   start a monitor for a switcher configured after app boot.
2. ``_ATEMEditDialog._apply`` persisted the new IP but never asked for a
   monitor restart, so a live monitor kept polling the previous IP while
   the UI showed the new one. Camera IP edits reconnect the camera worker;
   the ATEM edit silently did not.
"""
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
from unittest.mock import Mock

import pytest

from ui.config_edit_dialogs import _ATEMEditDialog


def _atem_dialog(service_result):
    service = Mock()
    service.set_atem_ip.return_value = service_result
    mw = SimpleNamespace(
        _camera_config=service,
        _do_restart_atem_monitor=Mock(),
    )
    dialog = Mock()
    dialog._mw = mw
    dialog._input.text.return_value = '192.0.2.50'
    return dialog, mw


@pytest.mark.parametrize('code', ['OK', 'PARTIAL_OK'])
def test_applied_atem_ip_restarts_the_monitor(code, monkeypatch):
    monkeypatch.setattr('ui.config_edit_dialogs.QMessageBox.warning', Mock())
    result = SimpleNamespace(code=code, message='')
    dialog, mw = _atem_dialog(result)
    _ATEMEditDialog._apply(dialog)
    assert dialog.accept.called
    mw._do_restart_atem_monitor.assert_called_once_with()


def test_rejected_atem_ip_does_not_restart_the_monitor():
    result = SimpleNamespace(code='INVALID_INPUT', message='Not saved.')
    dialog, mw = _atem_dialog(result)
    _ATEMEditDialog._apply(dialog)
    assert not dialog.accept.called
    mw._do_restart_atem_monitor.assert_not_called()


def test_first_configuration_starts_the_monitor():
    script = r'''
from types import SimpleNamespace
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
app = QApplication([])

# First-time configuration: no monitor yet, no fake, valid IP -> must start.
stub = SimpleNamespace(
    _shutting_down=False,
    _atem_restart_pending=False,
    _atem_monitor=None,
    _fake_atem=None,
    _atem_is_configured=lambda: True,
    _atem_dispatcher=Mock(),
    _start_atem_monitor=Mock(),
    _stop_and_replace_atem_monitor=lambda: MainWindow._stop_and_replace_atem_monitor(stub),
)
MainWindow._do_restart_atem_monitor(stub)
stub._start_atem_monitor.assert_called_once_with()
assert stub._atem_restart_pending is False

# Demo/sim: fake owns the ATEM surface -> restart path must NOT build a
# monitor (it would replace the panel's FakeATEM behind its back).
demo = SimpleNamespace(
    _shutting_down=False,
    _atem_restart_pending=False,
    _atem_monitor=None,
    _fake_atem=Mock(),
    _atem_is_configured=lambda: True,
    _atem_dispatcher=Mock(),
    _start_atem_monitor=Mock(),
    _stop_and_replace_atem_monitor=lambda: MainWindow._stop_and_replace_atem_monitor(demo),
)
MainWindow._do_restart_atem_monitor(demo)
demo._start_atem_monitor.assert_not_called()
assert demo._atem_restart_pending is False

# No valid IP configured: nothing to start.
unconfigured = SimpleNamespace(
    _shutting_down=False,
    _atem_restart_pending=False,
    _atem_monitor=None,
    _fake_atem=None,
    _atem_is_configured=lambda: False,
    _atem_dispatcher=Mock(),
    _start_atem_monitor=Mock(),
    _stop_and_replace_atem_monitor=lambda: MainWindow._stop_and_replace_atem_monitor(unconfigured),
)
MainWindow._do_restart_atem_monitor(unconfigured)
unconfigured._start_atem_monitor.assert_not_called()
assert unconfigured._atem_restart_pending is False
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
