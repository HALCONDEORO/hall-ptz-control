"""An invalid slot must never resolve to or repoint the second camera."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ptz.visca.manager import CameraManager


@pytest.mark.parametrize("key", [0, -1, 3, "cam1", None, True, False, 1.0, 2.0])
@pytest.mark.parametrize("operation", ["ip_for_key", "cam_id_for_key", "worker_by_key", "update_camera_ip", "update_camera_visca_id"])
def test_invalid_slot_denies_without_touching_other_camera(key, operation):
    manager = CameraManager(
        SimpleNamespace(ip="192.0.2.1", cam_id="81"),
        SimpleNamespace(ip="192.0.2.2", cam_id="82"),
    )
    manager.worker = Mock()
    args = (key, "192.0.2.3") if operation == "update_camera_ip" else ((key, "83") if operation == "update_camera_visca_id" else (key,))
    with pytest.raises(ValueError, match="camera key"):
        getattr(manager, operation)(*args)
    assert manager.ip_for_key(1) == "192.0.2.1"
    assert manager.ip_for_key(2) == "192.0.2.2"
    assert manager.cam_id_for_key(2) == "82"
    manager.worker.assert_not_called()
