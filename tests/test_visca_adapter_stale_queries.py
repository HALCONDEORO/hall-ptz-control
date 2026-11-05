"""Delayed display queries must not publish into a reconfigured camera slot."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.manager import CameraManager


@pytest.fixture
def rig(monkeypatch):
    manager = CameraManager(SimpleNamespace(ip="192.0.2.1", cam_id="81"),
                            SimpleNamespace(ip="192.0.2.2", cam_id="82"))
    adapter = ViscaCameraAdapter(manager, {1: ("192.0.2.1", "81"),
                                           2: ("192.0.2.2", "82")})
    # Prevent worker creation regardless of module reloads in other test files.
    monkeypatch.setattr(manager, "worker", Mock())
    pending = []

    class DeferredThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            pending.append(self.target)

    monkeypatch.setattr("adapters.visca_camera_adapter.threading.Thread", DeferredThread)
    adapter._query_zoom = Mock(return_value=8192)
    adapter._query_ae_and_exp_comp = Mock(return_value=("manual", 3))
    return adapter, manager, pending


@pytest.mark.parametrize("kind", ["zoom", "ae"])
@pytest.mark.parametrize("return_to_original", [False, True])
def test_reconfigured_query_does_not_publish(rig, kind, return_to_original):
    adapter, manager, pending = rig
    callback = Mock()
    if kind == "zoom":
        adapter.refresh_zoom_display(1, callback)
    else:
        adapter.async_refresh_ae_mode(1, callback)
    previous_ae = (manager.ae_mode[1], manager.exposure_level[1])
    manager.update_camera_ip(1, "192.0.2.3")
    adapter.update_camera_ip(1, "192.0.2.3")
    if return_to_original:
        manager.update_camera_ip(1, "192.0.2.1")
        adapter.update_camera_ip(1, "192.0.2.1")
    pending.pop(0)()
    callback.assert_not_called()
    assert manager.get_zoom(manager.ip_for_key(1)) is None
    assert (manager.ae_mode[1], manager.exposure_level[1]) == previous_ae
    acquire = getattr(manager, f"{kind}_query_try_acquire")
    release = getattr(manager, f"{kind}_query_release")
    # The obsolete result must still release its original endpoint lease.
    if return_to_original:
        assert acquire("192.0.2.1")
        release("192.0.2.1")


@pytest.mark.parametrize("kind", ["zoom", "ae"])
def test_current_query_still_publishes(rig, kind):
    adapter, manager, pending = rig
    callback = Mock()
    if kind == "zoom":
        adapter.refresh_zoom_display(1, callback)
    else:
        adapter.async_refresh_ae_mode(1, callback)
    pending.pop(0)()
    callback.assert_called_once()
    if kind == "zoom":
        assert manager.get_zoom("192.0.2.1") == 50
    else:
        assert manager.ae_mode[1] == "manual"
        assert manager.exposure_level[1] == 3


@pytest.mark.parametrize("kind", ["zoom", "ae"])
def test_reconfiguring_other_camera_keeps_current_query(rig, kind):
    adapter, manager, pending = rig
    callback = Mock()
    if kind == "zoom":
        adapter.refresh_zoom_display(1, callback)
    else:
        adapter.async_refresh_ae_mode(1, callback)
    manager.update_camera_ip(2, "192.0.2.4")
    adapter.update_camera_ip(2, "192.0.2.4")
    pending.pop(0)()
    callback.assert_called_once()


@pytest.mark.parametrize("kind", ["zoom", "ae"])
def test_live_config_generation_discards_round_trip_result(rig, monkeypatch, kind):
    import config

    adapter, manager, pending = rig
    adapter._cam_configs = None
    monkeypatch.setattr(config.CAM1, "ip", "192.0.2.1")
    monkeypatch.setattr(config.CAM1, "cam_id", "81")
    callback = Mock()
    if kind == "zoom":
        adapter.refresh_zoom_display(1, callback)
    else:
        adapter.async_refresh_ae_mode(1, callback)
    monkeypatch.setattr(config.CAM1, "ip", "192.0.2.3")
    adapter.update_camera_ip(1, "192.0.2.3")
    monkeypatch.setattr(config.CAM1, "ip", "192.0.2.1")
    adapter.update_camera_ip(1, "192.0.2.1")
    pending.pop(0)()
    callback.assert_not_called()
    assert manager.get_zoom("192.0.2.1") is None
