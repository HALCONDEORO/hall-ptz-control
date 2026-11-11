"""Settings Access tab must not leak an observer per dialog open.

ConfigDialog is rebuilt on every Settings open and stays parented to
MainWindow after close, so a subscription left behind accumulates dead
observers on the process-lifetime AccessModeService.
"""
import subprocess
import sys
import textwrap


def test_access_tab_unsubscribes_on_dialog_close():
    script = r'''
from pathlib import Path
from tempfile import TemporaryDirectory
import adapters.sim_mode as sim
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    from PyQt5.QtWidgets import QApplication
    app = QApplication([])
    from ui.main_window import MainWindow
    from ui.config_dialog import ConfigDialog
    window = MainWindow()
    svc = window._access_mode_svc
    base = len(svc._observers)
    d1 = ConfigDialog(window)
    mid = len(svc._observers)
    assert mid == base + 1, (base, mid)  # the open dialog observes live
    d1.reject()
    app.processEvents()
    after_one = len(svc._observers)
    d2 = ConfigDialog(window)
    d2.reject()
    app.processEvents()
    after_two = len(svc._observers)
    assert after_one == base, (base, after_one)
    assert after_two == base, (base, after_two)
print("OK")
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
