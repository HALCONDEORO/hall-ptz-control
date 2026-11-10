"""Moving one logical camera must not retire another camera's shared worker."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ptz.visca.manager import CameraManager


def manager():
    return CameraManager(SimpleNamespace(ip='192.0.2.11', cam_id='81'),
                         SimpleNamespace(ip='192.0.2.11', cam_id='82'))


def test_repoint_one_alias_keeps_original_worker_for_other_camera():
    cameras = manager()
    shared = Mock()
    replacement = Mock()
    cameras._workers['192.0.2.11'] = shared
    with patch.dict(CameraManager.worker.__globals__, CameraWorker=Mock(return_value=replacement)):
        cameras.update_camera_ip(1, '192.0.2.21')
        assert cameras.worker('192.0.2.11') is shared
        assert cameras.worker('192.0.2.21') is replacement
    shared.stop.assert_not_called()


def test_disable_one_alias_keeps_original_worker_until_last_alias_moves():
    cameras = manager()
    shared = Mock()
    cameras._workers['192.0.2.11'] = shared
    cameras.update_camera_ip(1, '')
    assert cameras.worker('192.0.2.11') is shared
    shared.stop.assert_not_called()
    cameras.update_camera_ip(2, '')
    shared.stop.assert_called_once()
    assert cameras._workers == {}


def test_shutdown_stops_preserved_shared_worker_once():
    cameras = manager()
    shared = Mock()
    cameras._workers['192.0.2.11'] = shared
    cameras.update_camera_ip(1, '')
    cameras.stop_all()
    shared.stop.assert_called_once()
