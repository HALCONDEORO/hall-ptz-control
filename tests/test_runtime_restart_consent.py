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
