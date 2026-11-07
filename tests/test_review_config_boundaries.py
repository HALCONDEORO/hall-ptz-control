"""Config/runtime identity regressions. No sockets or real hardware."""

from types import SimpleNamespace
from unittest.mock import Mock
import yaml
from application.camera_config_service import CameraConfigService
from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.manager import CameraManager
from config.loader import load_config


def rig(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        'site: {name: Test}\ncameras:\n  - {id: platform, role: platform, ip: 192.0.2.1, visca_id: "81"}\n  - {id: comments, role: comments, ip: 192.0.2.2, visca_id: "82"}\n'
    )
    cfg = SimpleNamespace(
        CAM1=SimpleNamespace(ip="192.0.2.1", cam_id="81"),
        CAM2=SimpleNamespace(ip="192.0.2.2", cam_id="82"),
    )
    mgr = CameraManager(cfg.CAM1, cfg.CAM2)
    mgr.worker = Mock()
    adapter = ViscaCameraAdapter(mgr, {1: ("192.0.2.1", "81"), 2: ("192.0.2.2", "82")})
    svc = CameraConfigService(
        config_path_provider=lambda: path,
        camera_manager_provider=lambda: mgr,
        camera_port_provider=lambda: adapter,
        config_module=cfg,
    )
    return path, cfg, mgr, adapter, svc


def test_visca_id_change_reaches_live_manager_and_adapter(tmp_path):
    path, cfg, mgr, adapter, svc = rig(tmp_path)
    assert svc.set_camera_visca_id(1, "83").ok
    assert cfg.CAM1.cam_id == "83"
    load_config(path)
    assert yaml.safe_load(path.read_text())["cameras"][0]["visca_id"] == "83"
    assert (mgr.cam_id_for_key(1), adapter._cam_info("cam1")[1]) == ("83", "83")


def test_service_rejects_id_that_loader_cannot_reload(tmp_path):
    _path, _cfg, _mgr, _adapter, svc = rig(tmp_path)
    assert not svc.set_camera_visca_id(1, "8182").ok


def test_service_rejects_duplicate_ip_before_collapsing_slots(tmp_path):
    _path, _cfg, mgr, _adapter, svc = rig(tmp_path)
    result = svc.set_camera_ip(1, "192.0.2.2")
    assert not result.ok
    assert mgr.ip_for_key(1) != mgr.ip_for_key(2)


def test_new_endpoint_does_not_inherit_exposure_or_backlight(tmp_path):
    _path, _cfg, mgr, adapter, svc = rig(tmp_path)
    mgr.ae_mode[1] = "manual"
    mgr.exposure_level[1] = 6
    mgr.focus_mode[1] = "manual"
    mgr.backlight_on[1] = True
    adapter._backlight_on["cam1"] = True
    assert svc.set_camera_ip(1, "192.0.2.3").ok
    assert (
        mgr.ae_mode[1],
        mgr.exposure_level[1],
        mgr.focus_mode[1],
        mgr.backlight_on[1],
        adapter._backlight_on.get("cam1", False),
    ) == ("auto", 0, "auto", False, False)


def test_duplicate_visca_id_is_rejected(tmp_path):
    path, _cfg, _mgr, _adapter, svc = rig(tmp_path)
    before = path.read_bytes()
    assert not svc.set_camera_visca_id(1, "82").ok
    assert path.read_bytes() == before


def test_peer_identity_comes_from_active_runtime_not_empty_globals(tmp_path):
    _path, cfg, _mgr, _adapter, svc = rig(tmp_path)
    cfg.CAM2.ip = ""
    cfg.CAM2.cam_id = ""
    assert not svc.set_camera_ip(1, "192.0.2.2").ok
    assert not svc.set_camera_visca_id(1, "82").ok


def test_id_change_retires_delayed_display_query(tmp_path, monkeypatch):
    _path, _cfg, mgr, adapter, svc = rig(tmp_path)
    pending = []

    class DeferredThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            pending.append(self.target)

    monkeypatch.setattr("adapters.visca_camera_adapter.threading.Thread", DeferredThread)
    adapter._query_zoom = Mock(return_value=8192)
    callback = Mock()
    adapter.refresh_zoom_display(1, callback)
    assert svc.set_camera_visca_id(1, "83").ok
    pending.pop()()
    callback.assert_not_called()
    assert mgr.get_zoom("192.0.2.1") is None
    assert mgr.zoom_query_try_acquire("192.0.2.1")
    mgr.zoom_query_release("192.0.2.1")


def test_confirmed_absolute_zoom_invalidates_previous_observation(tmp_path):
    _path, _cfg, mgr, adapter, _svc = rig(tmp_path)
    mgr.set_zoom("192.0.2.1", 20)
    adapter._send_confirmed = Mock(return_value=True)
    assert adapter.zoom_absolute("cam1", 80).ok
    assert mgr.get_zoom("192.0.2.1") != 20


def test_failed_ae_query_does_not_publish_invented_auto(tmp_path, monkeypatch):
    _path, _cfg, mgr, adapter, _svc = rig(tmp_path)
    mgr.ae_mode[1] = "manual"
    mgr.exposure_level[1] = 4
    pending = []

    class DeferredThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            pending.append(self.target)

    monkeypatch.setattr("adapters.visca_camera_adapter.threading.Thread", DeferredThread)
    monkeypatch.setattr(
        adapter, "_query_response", Mock(return_value=b"")
    )
    callback = Mock()
    adapter.async_refresh_ae_mode(1, callback)
    pending.pop()()
    assert mgr.ae_mode[1] == "manual"
    callback.assert_not_called()


def test_confirmed_zoom_retires_inflight_observation(tmp_path, monkeypatch):
    _path, _cfg, mgr, adapter, _svc = rig(tmp_path)
    pending = []

    class DeferredThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            pending.append(self.target)

    monkeypatch.setattr("adapters.visca_camera_adapter.threading.Thread", DeferredThread)
    adapter._query_zoom = Mock(return_value=3277)
    adapter._send_confirmed = Mock(return_value=True)
    callback = Mock()
    adapter.refresh_zoom_display(1, callback)
    assert adapter.zoom_absolute("cam1", 80).ok
    pending.pop()()
    callback.assert_not_called()
    assert mgr.get_zoom("192.0.2.1") is None
