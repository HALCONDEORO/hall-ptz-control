"""Tests for the STOP ALL button wiring (ui/stop_all_wiring.py)."""
import os
from pathlib import Path
import subprocess
import sys


def _run(script: str) -> None:
    result = subprocess.run([sys.executable, '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_stop_all_button_wired_in_clean_qt_process():
    script = r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication, QPushButton
import adapters.sim_mode as sim
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    app = QApplication([])
    from ui.main_window import MainWindow
    from application.runtime_safety_service import RuntimeSafetyService
    window = MainWindow()
    # bootstrap wired the product-level STOP authority into the window.
    assert isinstance(window._runtime_safety_svc, RuntimeSafetyService)
    buttons = [b for b in window._right_panel._container.findChildren(QPushButton)
               if b.text() == "STOP ALL"]
    assert len(buttons) == 1, "exactly one STOP ALL button in the right panel"
    btn = buttons[0]
    assert not btn.isHidden(), "STOP ALL must stay visible without a session"
    calls = []
    window._bus = Mock()
    window._bus.emit.side_effect = lambda *a, **k: calls.append(("emit", a, k))
    svc = Mock()
    svc.stop_all_cameras.side_effect = lambda: calls.append(("svc",)) or Mock(ok=True)
    window._runtime_safety_svc = svc
    btn.click()
    stops = [c for c in calls if c[0] == "emit"]
    assert [c[2].get("camera") for c in stops] == [1, 2], calls
    assert calls[-1][0] == "svc", "queued moves must be retired before STOP ALL"
    svc.stop_all_cameras.assert_called_once_with()
    from PyQt5.QtWidgets import QLabel
    notices = [l for l in window._right_panel._container.findChildren(QLabel)
               if l.styleSheet() and "E05050" in l.styleSheet()]
    assert len(notices) == 1 and notices[0].isHidden(), "no notice on success"
    window.hide()
    sim.deactivate()
'''
    _run(script)


def test_stop_all_partial_failure_does_not_raise():
    script = r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication, QPushButton
import adapters.sim_mode as sim
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    app = QApplication([])
    from ui.main_window import MainWindow
    from domain.supportability import OperationCode, OperationResult
    window = MainWindow()
    window._bus = Mock()
    svc = Mock()
    svc.stop_all_cameras.return_value = OperationResult.failure(
        code=OperationCode.CAMERA_COMMAND_FAILED,
        message="Failed to stop: cam2",
        operation="stop_all_cameras",
        target="all",
    )
    window._runtime_safety_svc = svc
    btn = [b for b in window._right_panel._container.findChildren(QPushButton)
           if b.text() == "STOP ALL"][0]
    btn.click()  # must not raise into the Qt slot
    svc.stop_all_cameras.assert_called_once_with()
    from PyQt5.QtWidgets import QLabel
    notices = [l for l in window._right_panel._container.findChildren(QLabel)
               if l.styleSheet() and "E05050" in l.styleSheet()]
    assert len(notices) == 1, "one failure notice label"
    assert not notices[0].isHidden(), "failure notice must be visible"
    assert "Failed to stop: cam2" in notices[0].text()
    window.hide()
    sim.deactivate()
'''
    _run(script)


def test_stop_all_repeated_failures_keep_one_timer_and_latest_notice():
    script = r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication, QPushButton, QLabel
from PyQt5 import QtCore
import adapters.sim_mode as sim
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    app = QApplication([])
    from ui.main_window import MainWindow
    from domain.supportability import OperationCode, OperationResult
    window = MainWindow()
    window._bus = Mock()
    svc = Mock()
    def fail(msg):
        return OperationResult.failure(
            code=OperationCode.CAMERA_COMMAND_FAILED, message=msg,
            operation="stop_all_cameras", target="all")
    window._runtime_safety_svc = svc
    panel = window._right_panel._container
    btn = [b for b in panel.findChildren(QPushButton) if b.text() == "STOP ALL"][0]
    notice = [l for l in panel.findChildren(QLabel)
              if l.styleSheet() and "E05050" in l.styleSheet()][0]
    svc.stop_all_cameras.return_value = fail("Failed to stop: cam1")
    btn.click()
    svc.stop_all_cameras.return_value = fail("Failed to stop: cam2")
    btn.click()
    assert "cam2" in notice.text() and not notice.isHidden()
    timers = [t for t in panel.findChildren(QtCore.QTimer)
              if t.isSingleShot() and t.interval() == 6000]
    assert len(timers) == 1, "one shared hide timer, restarted per failure"
    assert timers[0].isActive(), "hide timer re-armed for the latest failure"
    window.hide()
    sim.deactivate()
'''
    _run(script)


def test_stop_all_without_service_only_logs():
    script = r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication, QPushButton
import adapters.sim_mode as sim
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    app = QApplication([])
    from ui.main_window import MainWindow
    window = MainWindow()
    window._bus = Mock()
    window._runtime_safety_svc = None
    btn = [b for b in window._right_panel._container.findChildren(QPushButton)
           if b.text() == "STOP ALL"][0]
    btn.click()  # logs + shows the notice, still retires queued moves, never raises
    assert window._bus.emit.call_count == 2
    from PyQt5.QtWidgets import QLabel
    notice = [l for l in window._right_panel._container.findChildren(QLabel)
              if l.styleSheet() and "E05050" in l.styleSheet()][0]
    assert not notice.isHidden() and "unavailable" in notice.text()
    window.hide()
    sim.deactivate()
'''
    _run(script)
