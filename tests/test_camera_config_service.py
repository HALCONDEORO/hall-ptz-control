# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Tests for CameraConfigService — the single owner of camera/ATEM config writes (#893).

No Qt: the service is pure application logic. A temporary config.yaml and fake
CameraManager/CameraPort exercise validation, in-memory update, live repoint and
persistence, including the failure paths that must never lose the live change.
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest
import yaml

from application.camera_config_service import CameraConfigService
from domain.supportability import OperationCode


class _FakeRuntime:
    def __init__(self):
        self.calls = []

    def update_camera_ip(self, camera_index, new_ip):
        self.calls.append((camera_index, new_ip))


class _RaisingRuntime:
    def update_camera_ip(self, camera_index, new_ip):
        raise RuntimeError("link down")


@pytest.fixture
def fake_config():
    """A stand-in `config` module exposing only CAM1/CAM2/ATEM."""
    return types.SimpleNamespace(
        CAM1=types.SimpleNamespace(ip="", cam_id="81"),
        CAM2=types.SimpleNamespace(ip="", cam_id="82"),
        ATEM=types.SimpleNamespace(ip=""),
    )


@pytest.fixture
def config_yaml(tmp_path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "cameras": [
                    {"ip": "0.0.0.0", "visca_id": "81"},
                    {"ip": "0.0.0.0", "visca_id": "82"},
                ],
                "atem": {"ip": "0.0.0.0"},
            }
        ),
        encoding="utf-8",
    )
    return path


def _service(fake_config, config_yaml=None, manager=None, port=None):
    return CameraConfigService(
        config_path_provider=lambda: config_yaml,
        camera_manager_provider=lambda: manager,
        camera_port_provider=lambda: port,
        config_module=fake_config,
    )


# ── Validation ────────────────────────────────────────────────────────────────

def test_invalid_ip_is_rejected_and_nothing_changes(fake_config):
    svc = _service(fake_config)
    result = svc.set_camera_ip(1, "not-an-ip")
    assert not result.ok
    assert result.code == OperationCode.INVALID_INPUT
    assert fake_config.CAM1.ip == ""  # unchanged


def test_unknown_camera_number_is_rejected(fake_config):
    svc = _service(fake_config)
    assert not svc.set_camera_ip(3, "172.16.1.11").ok


def test_invalid_visca_id_is_rejected(fake_config):
    svc = _service(fake_config)
    result = svc.set_camera_visca_id(2, "zz")
    assert not result.ok
    assert fake_config.CAM2.cam_id == "82"  # unchanged


def test_invalid_atem_ip_is_rejected(fake_config):
    svc = _service(fake_config)
    assert not svc.set_atem_ip("999.1.1.1").ok
    assert fake_config.ATEM.ip == ""


# ── Happy path: memory + runtime + persistence ────────────────────────────────

def test_set_camera_ip_updates_memory_runtime_and_yaml(fake_config, config_yaml):
    manager, port = _FakeRuntime(), _FakeRuntime()
    svc = _service(fake_config, config_yaml, manager, port)

    result = svc.set_camera_ip(1, " 172.16.1.11 ")

    assert result.ok
    assert fake_config.CAM1.ip == "172.16.1.11"  # trimmed + stored
    assert manager.calls == [(1, "172.16.1.11")]  # live CameraManager repointed
    assert port.calls == [(1, "172.16.1.11")]     # live CameraPort repointed
    saved = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    assert saved["cameras"][0]["ip"] == "172.16.1.11"


def test_set_camera_two_targets_second_slot(fake_config, config_yaml):
    svc = _service(fake_config, config_yaml)
    assert svc.set_camera_ip(2, "172.16.1.12").ok
    saved = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    assert saved["cameras"][1]["ip"] == "172.16.1.12"


def test_set_visca_id_persists(fake_config, config_yaml):
    svc = _service(fake_config, config_yaml)
    assert svc.set_camera_visca_id(1, "0a").ok
    assert fake_config.CAM1.cam_id == "0a"
    saved = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    assert saved["cameras"][0]["visca_id"] == "0a"


def test_set_atem_ip_persists(fake_config, config_yaml):
    svc = _service(fake_config, config_yaml)
    assert svc.set_atem_ip("172.16.1.50").ok
    assert fake_config.ATEM.ip == "172.16.1.50"
    saved = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    assert saved["atem"]["ip"] == "172.16.1.50"


# ── Resilience: the live change is never lost ─────────────────────────────────

def test_missing_yaml_is_partial_not_failure(fake_config):
    svc = _service(fake_config, config_yaml=None)  # no path
    result = svc.set_camera_ip(1, "172.16.1.11")
    assert result.ok  # partial success is still ok=True
    assert result.code == OperationCode.PARTIAL_OK
    assert fake_config.CAM1.ip == "172.16.1.11"  # memory still updated


def test_runtime_error_does_not_break_the_config_change(fake_config, config_yaml):
    svc = _service(fake_config, config_yaml, manager=_RaisingRuntime(), port=_FakeRuntime())
    result = svc.set_camera_ip(1, "172.16.1.11")
    assert result.ok  # a failing live repoint must not fail the write
    assert fake_config.CAM1.ip == "172.16.1.11"
    saved = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    assert saved["cameras"][0]["ip"] == "172.16.1.11"


def test_absent_runtime_is_fine(fake_config, config_yaml):
    svc = _service(fake_config, config_yaml, manager=None, port=None)
    assert svc.set_camera_ip(1, "172.16.1.11").ok


# ── Simulation seeding is in-memory only ──────────────────────────────────────

def test_apply_simulation_ips_does_not_touch_yaml(fake_config, config_yaml):
    svc = _service(fake_config, config_yaml)
    svc.apply_simulation_ips("127.0.0.1", "127.0.0.2")
    assert (fake_config.CAM1.ip, fake_config.CAM2.ip) == ("127.0.0.1", "127.0.0.2")
    saved = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    assert saved["cameras"][0]["ip"] == "0.0.0.0"  # untouched


def test_same_ip_retries_save_without_repointing_live_session(fake_config, config_yaml):
    runtime = _FakeRuntime()
    fake_config.CAM1.ip = '192.0.2.11'
    service = _service(fake_config, config_yaml, manager=runtime)
    result = service.set_camera_ip(1, '192.0.2.11')
    assert result.code == 'OK'
    assert runtime.calls == []
    assert yaml.safe_load(config_yaml.read_text())['cameras'][0]['ip'] == '192.0.2.11'


@pytest.mark.parametrize('failed_target', ['manager', 'port'])
def test_same_ip_retries_failed_runtime_repoint_then_becomes_noop(fake_config, config_yaml, failed_target):
    class Runtime(_FakeRuntime):
        def __init__(self, fail):
            super().__init__()
            self.fail = fail
            self.ip = '192.0.2.10'
        def update_camera_ip(self, camera_index, new_ip):
            super().update_camera_ip(camera_index, new_ip)
            if self.fail:
                self.fail = False
                raise RuntimeError('first repoint failed')
            self.ip = new_ip
        def ip_for_key(self, key):
            return self.ip if key == 1 else '192.0.2.12'
    manager = Runtime(failed_target == 'manager')
    port = Runtime(failed_target == 'port')
    service = _service(fake_config, config_yaml, manager=manager, port=port)
    assert service.set_camera_ip(1, '192.0.2.11').ok
    assert service.set_camera_ip(1, '192.0.2.11').ok
    assert manager.ip == port.ip == '192.0.2.11'
    assert len(manager.calls) == len(port.calls) == 2
    assert service.set_camera_ip(1, '192.0.2.11').ok
    assert len(manager.calls) == len(port.calls) == 2


def test_same_ip_reconciles_runtime_mismatch_without_prior_pending_flag(fake_config, config_yaml):
    class Runtime(_FakeRuntime):
        def ip_for_key(self, key):
            return '192.0.2.10' if key == 1 else '192.0.2.12'
    runtime = Runtime()
    fake_config.CAM1.ip = '192.0.2.11'
    service = _service(fake_config, config_yaml, manager=runtime)
    assert service.set_camera_ip(1, '192.0.2.11').ok
    assert runtime.calls == [(1, '192.0.2.11')]
