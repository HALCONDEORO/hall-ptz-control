"""Always-open loading must keep the unused weekly schedule disabled."""
import os
from pathlib import Path
import subprocess
import sys


def test_always_open_controls_in_clean_qt_process():
    script = r'''
from PyQt5.QtWidgets import QApplication
from unittest.mock import patch
from ui.schedule_dialog import ScheduleDialog
app = QApplication([])
schedule = {'always_bypass': True, 'monday': {
    'enabled': True, 'start': '09:00', 'end': '17:00'}}
with patch('ui.schedule_dialog.load_schedule', return_value=schedule):
    dialog = ScheduleDialog()
checkbox, start, end = dialog._rows['monday']
assert checkbox.isChecked()
assert not checkbox.isEnabled()
assert not start.isEnabled(), 'saved enabled day re-enables start while always-open is active'
assert not end.isEnabled(), 'saved enabled day re-enables end while always-open is active'
dialog._toggle_always()
assert checkbox.isEnabled() and start.isEnabled() and end.isEnabled()
dialog.close()
'''
    result = subprocess.run([sys.executable, '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
