"""Reusing a recently retired IP must not open a second live VISCA session."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch
from ptz.visca.manager import CameraManager


def test_reassign_back_while_old_worker_stop_in_flight_never_creates_overlap():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.11', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.12', cam_id='82'))
    entered, release = threading.Event(), threading.Event()
    old = Mock()
    old._thread.is_alive.return_value = False
    def slow_stop():
        entered.set()
        assert release.wait(2)
    old.stop.side_effect = slow_stop
    manager._workers['192.0.2.11'] = old
    errors = []
    def reassign():
        try:
            manager.update_camera_ip(1, '192.0.2.21')
        except Exception as exc:
            errors.append(exc)
    with patch.dict(CameraManager.worker.__globals__, CameraWorker=Mock()) as globals_:
        factory = globals_['CameraWorker']
        thread = threading.Thread(target=reassign)
        thread.start()
        try:
            assert entered.wait(1)
            manager.update_camera_ip(1, '192.0.2.11')
            assert not any(call.args == ('192.0.2.11',) for call in factory.call_args_list), (
                'Replacement opened old IP while its previous worker was still stopping')
        finally:
            release.set()
            thread.join(2)
        assert not errors
        assert any(call.args == ('192.0.2.11',) for call in factory.call_args_list)
        assert manager._workers['192.0.2.11'] is factory.return_value


def test_join_timeout_keeps_endpoint_reserved_until_old_thread_dies():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.11', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.12', cam_id='82'))
    old = Mock()
    old._thread.is_alive.return_value = True
    manager._workers['192.0.2.11'] = old
    with patch.dict(CameraManager.worker.__globals__, CameraWorker=Mock()) as globals_:
        factory = globals_['CameraWorker']
        manager.update_camera_ip(1, '192.0.2.21')
        factory.reset_mock()
        manager.update_camera_ip(1, '192.0.2.11')
        assert manager.worker_is_healthy(1, 10) is False
        assert manager.restart_worker(1) is False
        factory.assert_not_called()
        old._thread.is_alive.return_value = False
        assert manager.restart_worker(1) is True
        factory.assert_called_once_with('192.0.2.11')


def test_terminal_shutdown_also_retires_join_timeout_workers():
    manager = CameraManager(SimpleNamespace(ip='192.0.2.11', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.12', cam_id='82'))
    old = Mock()
    old._thread.is_alive.return_value = True
    manager._workers['192.0.2.11'] = old
    with patch.dict(CameraManager.worker.__globals__, CameraWorker=Mock()) as globals_:
        manager.update_camera_ip(1, '192.0.2.21')
        new = globals_['CameraWorker'].return_value
        manager.stop_all()
        assert old.stop.call_count == 2
        new.stop.assert_called_once()
