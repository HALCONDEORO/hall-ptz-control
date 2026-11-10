"""Late startup delivery must not restart camera work after close begins."""
import os
from pathlib import Path
import subprocess
import sys


def test_late_startup_and_prompt_are_inert_after_shutdown():
    script = r'''
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PyQt5.QtWidgets import QApplication, QWidget
from ui.main_window import MainWindow
from ui.startup_power_prompt import maybe_prompt_power_on
import config
app = QApplication([])
config.CAM1.ip = '192.0.2.11'
w = QWidget()
w.session_active = False
w._session = SimpleNamespace(ToggleSession=Mock())
w._shutting_down = False
maybe_prompt_power_on(w)
box = w._startup_power_prompt
w._shutting_down = True
box.buttons()[0].click()
app.processEvents()
w._session.ToggleSession.assert_not_called()
assert w._startup_power_prompt is None
maybe_prompt_power_on(w)
assert w._startup_power_prompt is None
for sim in (False, True):
    stub = SimpleNamespace(_shutting_down=True, _splash_overlay=Mock(),
        _refresh_zoom=Mock(), _right_panel=Mock(), _maybe_prompt_power_on=Mock(),
        session_active=False, _session=SimpleNamespace(ToggleSession=Mock()))
    with patch('adapters.sim_mode.is_active', return_value=sim):
        MainWindow._on_startup_done(stub)
    stub._refresh_zoom.assert_not_called()
    stub._maybe_prompt_power_on.assert_not_called()
    stub._session.ToggleSession.assert_not_called()
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
