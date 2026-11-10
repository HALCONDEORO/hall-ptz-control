"""Restart must not spawn or change profile before close confirmation."""
import os
from pathlib import Path
import subprocess
import sys


def test_cancelled_close_keeps_profile_and_never_spawns():
    script = r'''
from types import SimpleNamespace
from unittest.mock import Mock, patch
from ui.config_dialog import ConfigDialog
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
app = QApplication([])
dialog = QDialog()
for target in ('production', 'demo', 'simulation'):
    window = SimpleNamespace(close=Mock(return_value=False))
    with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes), patch('subprocess.Popen') as spawn, patch('adapters.sim_mode.is_active', return_value=target == 'production'), patch('adapters.sim_mode.activate') as activate, patch('adapters.sim_mode.deactivate') as deactivate:
        ConfigDialog._restart_in_runtime_mode(dialog, window, target)
    spawn.assert_not_called()
    activate.assert_not_called()
    deactivate.assert_not_called()
'''
    _run(script)


def test_accepted_restart_uses_root_entry_and_deferred_launch():
    script = r'''
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from ui.config_dialog import ConfigDialog
from ui.runtime_restart import prepare_runtime_restart, launch_pending_restart
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
app = QApplication([])
dialog = QDialog()
window = SimpleNamespace()
order = []
def close():
    order.append('close_confirmed')
    assert prepare_runtime_restart(window)
    order.append('hardware_cleanup')
    launch_pending_restart(window)
    return True
window.close = close
with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes), patch('adapters.sim_mode.is_active', return_value=False), patch('adapters.sim_mode.activate', side_effect=lambda: order.append('activate')), patch('subprocess.Popen', side_effect=lambda *a, **k: order.append('spawn')) as spawn:
    ConfigDialog._restart_in_runtime_mode(dialog, window, 'simulation')
assert order == ['close_confirmed', 'activate', 'hardware_cleanup', 'spawn']
command = spawn.call_args.args[0]
assert Path(command[1]).is_file()
assert Path(command[1]).parent.name != 'ui'
assert spawn.call_args.kwargs['env']['KHPTZ_PROFILE'] == 'simulation'
'''
    _run(script)


def _run(script):
    result = subprocess.run([sys.executable, '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_failed_demo_reset_preserves_existing_simulation_state():
    script = r'''
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from ui.runtime_restart import queue_runtime_restart, prepare_runtime_restart
app = QApplication([])
for initially_active in (False, True):
    for outcome in (SimpleNamespace(success=False, error='reset failed'), RuntimeError('reset raised')):
        state = {'active': initially_active}
        def activate():
            state['active'] = True
        window = SimpleNamespace()
        window.close = lambda: prepare_runtime_restart(window)
        reset_kwargs = ({'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome})
        with patch('adapters.sim_mode.is_active', side_effect=lambda: state['active']), patch('adapters.sim_mode.activate', side_effect=activate) as activation, patch('adapters.sim_mode.deactivate') as deactivation, patch('application.demo_reset_service.DemoResetService.reset', **reset_kwargs), patch.object(QMessageBox, 'warning'), patch('subprocess.Popen') as spawn:
            queue_runtime_restart(QDialog(), window, 'demo')
        assert state['active'] == initially_active, 'Failed reset changed production camera profile'
        activation.assert_not_called()
        deactivation.assert_not_called()
        spawn.assert_not_called()
        assert window._pending_admin_restart is None
        assert window._pending_runtime_prepare is None
        assert window._pending_admin_restart_env is None
'''
    _run(script)


def test_successful_demo_reset_precedes_activation():
    script = r'''
from types import SimpleNamespace
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication, QDialog
from ui.runtime_restart import queue_runtime_restart, prepare_runtime_restart
app = QApplication([])
order = []
window = SimpleNamespace()
window.close = lambda: prepare_runtime_restart(window)
def reset():
    order.append('reset')
    return SimpleNamespace(success=True)
with patch('adapters.sim_mode.is_active', return_value=False), patch('adapters.sim_mode.activate', side_effect=lambda: order.append('activate')), patch('application.demo_reset_service.DemoResetService.reset', side_effect=reset):
    queue_runtime_restart(QDialog(), window, 'demo')
assert order == ['reset', 'activate']
assert window._pending_admin_restart_env['KHPTZ_PROFILE'] == 'demo'
'''
    _run(script)
