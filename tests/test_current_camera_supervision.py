# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Recovery must never resurrect a retired camera endpoint."""
from types import SimpleNamespace
from unittest.mock import Mock
import threading

import pytest

from config import CameraConfig
from ptz.visca.manager import CameraManager


def manager():
    return CameraManager(CameraConfig(ip="camera-one", cam_id="81"),
                         CameraConfig(ip="camera-two", cam_id="82"))


def worker(alive=True, age=0):
    return SimpleNamespace(_thread=SimpleNamespace(is_alive=lambda: alive),
                           progress_age=lambda: age, restart=Mock(return_value=True),
                           stop=Mock())


@pytest.mark.parametrize("key", [1, 2])
def test_current_worker_not_retired_worker_is_recovered(key):
    mgr = manager()
    old, current = worker(False), worker(False)
    with mgr._workers_lock:
        mgr._workers["retired"] = old
        mgr._workers[mgr.ip_for_key(key)] = current
    assert mgr.worker_is_healthy(key, 30) is False
    assert mgr.restart_worker(key) is True
    current.restart.assert_called_once_with()
    old.restart.assert_not_called()


@pytest.mark.parametrize("alive,age,healthy", [(True, 0, True), (True, 30, False), (False, 0, False)])
def test_health_still_requires_progress_and_live_thread(alive, age, healthy):
    mgr = manager()
    mgr._workers["camera-one"] = worker(alive, age)
    assert mgr.worker_is_healthy(1, 30) is healthy


def test_empty_or_lazy_endpoint_does_not_create_network_worker():
    mgr = manager()
    assert mgr.worker_is_healthy(1, 30) is True
    assert mgr.restart_worker(1) is True
    mgr._cam1_ip = ""
    assert mgr.worker_is_healthy(1, 30) is True
    assert mgr.restart_worker(1) is True
    assert mgr._workers == {}


def test_restart_failure_is_not_reported_as_success():
    mgr = manager()
    current = worker(False)
    current.restart.return_value = False
    mgr._workers["camera-one"] = current
    assert mgr.restart_worker(1) is False


def test_reassignment_cannot_retire_worker_mid_restart():
    mgr = manager()
    current = worker(False)
    entered, release, reassigned = threading.Event(), threading.Event(), threading.Event()
    def restart():
        entered.set()
        assert release.wait(2)
        return True
    current.restart.side_effect = restart
    mgr._workers["camera-one"] = current
    mgr.worker = Mock()
    recovery = threading.Thread(target=lambda: mgr.restart_worker(1))
    def update():
        mgr.update_camera_ip(1, "replacement")
        reassigned.set()
    recovery.start()
    assert entered.wait(2)
    update_thread = threading.Thread(target=update)
    update_thread.start()
    try:
        assert not reassigned.wait(0.05)
    finally:
        release.set()
        recovery.join(2)
        update_thread.join(2)
    assert reassigned.is_set()
    current.stop.assert_called_once_with()
    mgr.worker.assert_called_once_with("replacement")
    mgr.restart_worker(1)
    current.restart.assert_called_once_with()
