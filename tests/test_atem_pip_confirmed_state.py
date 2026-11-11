"""Manual PiP requests are not confirmation of physical switcher state."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from domain.ports import AtemCommandResult


@pytest.mark.parametrize('requested,confirmed', [(True, False), (False, True)])
@pytest.mark.parametrize('succeeded', [True, False])
def test_production_pip_waits_for_confirmed_state(requested, confirmed, succeeded):
    from ui.main_window import MainWindow
    result = AtemCommandResult(ok=succeeded, command='set_pip_enabled')
    window = SimpleNamespace(
        _atem_write_adapter=SimpleNamespace(set_pip_enabled=Mock(return_value=result)),
        _pip_active=confirmed,
        _notify_pip_state=Mock(),
    )
    MainWindow.pip_set(window, requested)
    window._atem_write_adapter.set_pip_enabled.assert_called_once_with(requested)
    assert window._pip_active is confirmed
    window._notify_pip_state.assert_not_called()


def test_demo_pip_still_updates_immediately():
    from ui.main_window import MainWindow
    window = SimpleNamespace(_atem_write_adapter=None,
        _atem_dispatcher=SimpleNamespace(on_pip_changed=Mock()),
        _pip_active=False, _notify_pip_state=Mock())
    MainWindow.pip_set(window, True)
    assert window._pip_active is True
    window._notify_pip_state.assert_called_once_with(True)
    state = window._atem_dispatcher.on_pip_changed.call_args.args[0]
    assert state.enabled is True


def test_real_panel_keeps_confirmed_indicator_after_failed_request():
    import os
    from pathlib import Path
    import subprocess
    import sys
    script = r'''
from types import SimpleNamespace
from PyQt5.QtWidgets import QApplication
from domain.ports import AtemCommandResult
from domain.supportability import OperationResult
from ui.atem_admin_panel import AtemAdminPanel
from ui.main_window import MainWindow
app = QApplication([])
panel = AtemAdminPanel(SimpleNamespace(read_status=lambda: OperationResult.success('status', 'atem', data={'connected': True})), SimpleNamespace())
panel.set_pip_state(False)
window = SimpleNamespace(_atem_write_adapter=SimpleNamespace(set_pip_enabled=lambda _: AtemCommandResult(ok=False, command='set_pip_enabled', message='Disconnected')),
    _pip_active=False, _notify_pip_state=panel.set_pip_state)
MainWindow.pip_set(window, True)
assert panel._lbl_pip_state.text() == 'PiP: ○  inactivo'
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
