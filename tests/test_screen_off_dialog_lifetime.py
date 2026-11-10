"""A hidden finished countdown must never emit a later contradictory result."""
import os
from pathlib import Path
import subprocess
import sys


def test_all_dialog_finish_paths_stop_countdown_in_clean_qt_process():
    script = r'''
from PyQt5.QtWidgets import QApplication, QWidget, QDialog
from ui.screen_off_dialog import ScreenOffDialog
app = QApplication([])
parent = QWidget()
for action in ('no', 'yes', 'reject', 'accept', 'close'):
    dialog = ScreenOffDialog(parent, timeout_secs=1)
    dialog.show()
    app.processEvents()
    outcomes = []
    dialog.finished.connect(outcomes.append)
    if action == 'no': dialog._btn_no.click()
    elif action == 'yes': dialog._btn_yes.click()
    else: getattr(dialog, action)()
    app.processEvents()
    assert not dialog._timer.isActive(), action + ' left hidden countdown running'
    expected = QDialog.Accepted if action in ('yes', 'accept') else QDialog.Rejected
    assert outcomes == [expected]
    assert dialog.result() == expected
parent.close()
'''
    result = subprocess.run([sys.executable, '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
