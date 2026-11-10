"""Current transport state must not be lost before GUI signal wiring."""
from types import SimpleNamespace
from unittest.mock import Mock

from domain.camera_state import CameraConnectionState
from ui.camera_led_wiring import wire_camera_worker


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        for slot in self.slots:
            slot(*args)


def test_already_connected_worker_is_observed_without_waiting_for_a_reconnect():
    worker = SimpleNamespace(ip='192.0.2.1', is_connected=True,
                             _connection_state=CameraConnectionState.CONNECTED,
                             signals=SimpleNamespace(connection_changed=Signal(),
                                 connection_state_changed=Signal(), visca_error=Signal()))
    manager = SimpleNamespace(worker_is_current=lambda candidate: candidate is worker,
                              is_connected=lambda ip: True, cam_key=lambda ip: 1)
    window = SimpleNamespace(_cameras=manager, Cam1=Mock(), Cam2=Mock(),
                             _on_cam_connected=Mock(), _on_cam_connection_changed=Mock(),
                             _on_visca_speed_error=Mock())
    wire_camera_worker(window, worker)
    window._on_cam_connection_changed.assert_called_once_with(True, worker.ip)
    window._on_cam_connected.assert_called_once_with(True, worker.ip)
    window.Cam1.set_connecting.assert_called_once_with(False)


def test_retired_worker_initial_snapshot_is_ignored():
    worker = SimpleNamespace(ip='192.0.2.1', is_connected=True,
                             _connection_state=CameraConnectionState.CONNECTED,
                             signals=SimpleNamespace(connection_changed=Signal(),
                                 connection_state_changed=Signal(), visca_error=Signal()))
    window = SimpleNamespace(_cameras=SimpleNamespace(worker_is_current=lambda worker: False),
                             Cam1=Mock(), Cam2=Mock(),
                             _on_cam_connected=Mock(), _on_cam_connection_changed=Mock(),
                             _on_visca_speed_error=Mock())
    wire_camera_worker(window, worker)
    window._on_cam_connection_changed.assert_not_called()
    window._on_cam_connected.assert_not_called()
    window.Cam1.set_connecting.assert_not_called()
