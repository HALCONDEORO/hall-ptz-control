"""Wall-clock corrections cannot change camera inactivity power-off timing."""
import os
from pathlib import Path
import subprocess
import sys


def test_inactivity_clock_in_clean_qt_process():
    script = r'''
from types import SimpleNamespace
from unittest.mock import Mock, patch
from ui.main_window import MainWindow

# No widget construction or hardware. Simulate independent elapsed/wall clocks.
def window():
    win = SimpleNamespace(_INACTIVITY_TIMEOUT=7200, session_active=True, _session=Mock())
    with patch('ui.main_window.time.time', return_value=10000), patch('ui.main_window.time.monotonic', return_value=100):
        MainWindow._record_activity(win)
    return win

for wall in (10000 + 10800, 10000 - 10800):
    win = window()
    with patch('ui.main_window.time.time', return_value=wall), patch('ui.main_window.time.monotonic', return_value=101):
        MainWindow._check_inactivity(win)
    win._session.shutdown.assert_not_called()

win = window()
with patch('ui.main_window.time.time', return_value=10001), patch('ui.main_window.time.monotonic', return_value=7301):
    MainWindow._check_inactivity(win)
win._session.shutdown.assert_called_once_with('inactivity')

win = window()
win.session_active = False
with patch('ui.main_window.time.monotonic', return_value=7301):
    MainWindow._check_inactivity(win)
win._session.shutdown.assert_not_called()
'''
    result = subprocess.run([sys.executable, '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
