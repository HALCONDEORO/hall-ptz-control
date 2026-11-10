"""Retired worker notifications must not alter a replacement at the same IP."""
from types import SimpleNamespace
from unittest.mock import Mock, patch


class Signal:
    def __init__(self):
        self.slots = []
    def connect(self, slot):
        self.slots.append(slot)
    def emit(self, *args):
        for slot in self.slots:
            slot(*args)


def test_retired_worker_same_ip_does_not_publish_false_disconnect_to_ui():
    from conftest import ensure_real_qt
    ensure_real_qt()
    from ui.main_window import MainWindow
    old = SimpleNamespace(ip='192.0.2.11', signals=SimpleNamespace(
        visca_error=Signal(), connection_changed=Signal(), connection_state_changed=Signal()))
    replacement = object()
    from ptz.visca.manager import CameraManager
    manager = CameraManager(SimpleNamespace(ip=old.ip, cam_id='81'),
                            SimpleNamespace(ip='192.0.2.12', cam_id='82'))
    manager._workers[old.ip] = old
    window = SimpleNamespace(_cameras=manager,
        _on_visca_speed_error=Mock(), _on_cam_connected=Mock(), _on_cam_connection_changed=Mock())
    with patch('ui.camera_led_wiring.wire_connecting_led'):
        MainWindow._on_worker_ready(window, old)
    old.signals.connection_changed.emit(True)
    window._on_cam_connected.assert_called_once_with(True, old.ip)
    window._on_cam_connection_changed.assert_called_once_with(True, old.ip)
    window._on_cam_connected.reset_mock()
    window._on_cam_connection_changed.reset_mock()
    # Equivalent to delivery of an already queued Qt notification after the
    # endpoint was retired then reused by a new worker.
    window._cameras._workers[old.ip] = replacement
    old.signals.connection_changed.emit(False)
    window._on_cam_connected.assert_not_called()
    window._on_cam_connection_changed.assert_not_called()
    old.signals.visca_error.emit(old.ip, 'move')
    window._on_visca_speed_error.assert_not_called()


def test_real_qt_queued_disconnect_is_checked_at_delivery():
    import threading
    from conftest import ensure_real_qt
    ensure_real_qt()
    from PyQt5.QtCore import QObject, pyqtSignal
    from PyQt5.QtWidgets import QApplication
    from ptz.visca.manager import CameraManager
    from ui.camera_led_wiring import wire_camera_worker
    app = QApplication.instance() or QApplication([])
    class Signals(QObject):
        connection_changed = pyqtSignal(bool)
        connection_state_changed = pyqtSignal(object)
        visca_error = pyqtSignal(str, str)
    old = SimpleNamespace(ip='192.0.2.11', signals=Signals())
    manager = CameraManager(SimpleNamespace(ip=old.ip, cam_id='81'),
                            SimpleNamespace(ip='192.0.2.12', cam_id='82'))
    manager._workers[old.ip] = old
    window = SimpleNamespace(_cameras=manager, _on_visca_speed_error=Mock(),
        _on_cam_connected=Mock(), _on_cam_connection_changed=Mock(), Cam1=Mock(), Cam2=Mock())
    wire_camera_worker(window, old)
    from domain.camera_state import CameraConnectionState
    def emit():
        old.signals.connection_changed.emit(False)
        old.signals.connection_state_changed.emit(CameraConnectionState.CONNECTING)
    thread = threading.Thread(target=emit)
    thread.start()
    thread.join(2)
    assert not thread.is_alive()
    manager._workers[old.ip] = object()
    app.processEvents()
    window._on_cam_connected.assert_not_called()
    window._on_cam_connection_changed.assert_not_called()
    window.Cam1.set_connecting.assert_not_called()
