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
    from domain.call_set_policy import OperatingMode
    window._access_mode_svc.set_mode(OperatingMode.ADMIN)
    # bootstrap wired the product-level STOP authority into the window.
    assert isinstance(window._runtime_safety_svc, RuntimeSafetyService)
    buttons = [b for b in window._right_panel._container.findChildren(QPushButton)
               if b.text() == "STOP ALL"]
    assert len(buttons) == 1, "exactly one STOP ALL button in the right panel"
    btn = buttons[0]
    assert not btn.isHidden(), "ADMIN STOP ALL must stay visible without a session"
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
    from domain.call_set_policy import OperatingMode
    window._access_mode_svc.set_mode(OperatingMode.ADMIN)
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
    from domain.call_set_policy import OperatingMode
    window._access_mode_svc.set_mode(OperatingMode.ADMIN)
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
    from domain.call_set_policy import OperatingMode
    window._access_mode_svc.set_mode(OperatingMode.ADMIN)
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


def test_stop_all_tracks_initial_role_and_inline_role_changes():
    _run(r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication, QPushButton, QLabel
import adapters.sim_mode as sim
from application.access_mode_service import AccessModeService
from domain.call_set_policy import OperatingMode
from ui.stop_all_wiring import connect_stop_all
with TemporaryDirectory() as root:
    sim._APP_DIR = Path(root)
    sim.BACKUP = Path(root) / 'backup.json'
    sim.activate()
    app = QApplication([])
    from ui.main_window import MainWindow
    window = MainWindow()
    access = window._access_mode_svc
    access.set_mode(OperatingMode.USER)
    btn = next(b for b in window._right_panel._container.findChildren(QPushButton) if b.text() == 'STOP ALL')
    assert btn.isHidden()
    # USER retains release STOP for the moved camera, without an all-stop button.
    from core.events import EventType
    window._bus.emit = Mock()
    window._right_panel._joystick.stop_handler()
    assert window._bus.emit.call_args.args[0] == EventType.CAMERA_STOP
    assert window._bus.emit.call_args.kwargs['camera'] in (1, 2)
    window._on_role_elevation_success()
    assert not btn.isHidden()
    svc = Mock()
    svc.stop_all_cameras.return_value = Mock(ok=False, message='cam2 not confirmed')
    window._runtime_safety_svc = svc
    btn.click()
    notice = next(l for l in window._right_panel._container.findChildren(QLabel) if 'E05050' in l.styleSheet())
    assert not notice.isHidden()
    window._exit_admin_mode()
    assert btn.isHidden() and notice.isHidden()
    window._on_role_elevation_success()
    assert not btn.isHidden() and notice.isHidden()
    # Exercise initial registration in both roles without persisted state assumptions.
    from types import SimpleNamespace
    from PyQt5.QtWidgets import QWidget, QVBoxLayout
    for role in (OperatingMode.USER, OperatingMode.ADMIN):
        container = QWidget()
        layout = QVBoxLayout(container)
        anchor = QLabel(container)
        layout.addWidget(anchor)
        service = AccessModeService(Path(root) / (role.value + '.json'))
        service.set_mode(role)
        fixture = SimpleNamespace(_right_panel=SimpleNamespace(_container=container, _no_camera_label=anchor), _access_mode_svc=service)
        new_button = connect_stop_all(fixture)
        assert new_button.isHidden() == (role == OperatingMode.USER)
        container.deleteLater()
    window.hide()
    sim.deactivate()
''')
