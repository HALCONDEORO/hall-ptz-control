"""Settings camera diagnostics never wait for network on Qt's thread."""
import os
from pathlib import Path
import subprocess
import sys


def test_focus_test_uses_worker_and_stops_after_dialog_finishes():
    script = r'''
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PyQt5.QtWidgets import QApplication, QPushButton
from PyQt5.QtCore import QTimer
import adapters.sim_mode as sim
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    app = QApplication([])
    from ui.main_window import MainWindow
    from ui.config_dialog import ConfigDialog
    window = MainWindow()
    entered, release = threading.Event(), threading.Event()
    calls = []
    def operation(cam):
        calls.append((cam, threading.current_thread()))
        entered.set()
        release.wait(.3)
        return SimpleNamespace(ok=True)
    port = Mock()
    port.focus_auto = operation
    window._camera_port = port
    dialog = ConfigDialog(window)
    run = next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Run Test')
    run.click()
    deadline = time.monotonic() + 1
    while not entered.is_set() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert entered.is_set()
    assert calls[0][1] is not threading.current_thread(), 'Focus command blocked Qt thread'
    seen = []
    QTimer.singleShot(0, lambda: seen.append(True))
    app.processEvents()
    assert seen == [True]
    dialog.reject()
    release.set()
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    port.one_push_af.assert_not_called()
    port.focus_manual.assert_not_called()
    port.brightness_down.assert_not_called()
    window.hide()
    sim.deactivate()
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_diagnostic_runner_finishes_sequence_and_contains_port_exception():
    script = r'''
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication, QDialog
from ui.camera_diagnostic_runner import CameraDiagnosticRunner
app = QApplication([])
owner = QDialog()
calls, results, completed = [], [], []
def command(cam):
    calls.append((cam, threading.current_thread()))
    if len(calls) == 2:
        raise OSError('test transport unavailable')
    return SimpleNamespace(ok=True)
port = Mock(first=command, second=command, third=command)
runner = CameraDiagnosticRunner(owner, port, 'cam2', [('first', 0), ('second', 1), ('third', 2)])
runner.result.connect(lambda i, ok: results.append((i, ok, threading.current_thread())))
runner.complete.connect(lambda: completed.append(True))
runner.start()
deadline = time.monotonic() + 3
while not completed and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(.005)
assert completed == [True]
assert len(calls) == 3
assert all(cam == 'cam2' and thread is not threading.current_thread() for cam, thread in calls)
assert [(i, ok) for i, ok, _ in results] == [(0, True), (1, False), (2, True)]
assert all(thread is threading.current_thread() for _, _, thread in results)
# Accepting before the first timer prevents the entire sequence.
owner2 = QDialog()
port2 = Mock()
runner2 = CameraDiagnosticRunner(owner2, port2, 'cam1', [('first', 0)])
runner2.start()
owner2.accept()
deadline = time.monotonic() + .2
while time.monotonic() < deadline:
    app.processEvents()
    time.sleep(.005)
port2.first.assert_not_called()
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
