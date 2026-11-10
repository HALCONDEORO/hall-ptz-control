# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Reconfiguration must not inherit another endpoint's cache or query lease."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ptz.visca.manager import CameraManager


@pytest.fixture
def manager():
    return CameraManager(
        SimpleNamespace(ip="192.0.2.1", cam_id="81"),
        SimpleNamespace(ip="192.0.2.2", cam_id="81"),
    )


@pytest.mark.parametrize("kind", ["zoom", "ae"])
def test_retired_query_can_release_without_blocking_new_endpoint(manager, kind):
    acquire = getattr(manager, f"{kind}_query_try_acquire")
    release = getattr(manager, f"{kind}_query_release")
    assert acquire("192.0.2.1")
    with patch("ptz.visca.manager.CameraWorker"):
        manager.update_camera_ip(1, "192.0.2.3")
    assert acquire("192.0.2.3")
    release("192.0.2.1")
    assert not acquire("192.0.2.3"), "retired release must not clear the new lease"
    release("192.0.2.3")
    assert acquire("192.0.2.3")


def test_new_endpoint_has_no_old_zoom_cache(manager):
    manager.set_zoom("192.0.2.1", 78)
    manager.set_zoom("192.0.2.2", 25)
    with patch("ptz.visca.manager.CameraWorker"):
        manager.update_camera_ip(1, "192.0.2.3")
    assert manager.get_zoom("192.0.2.3") is None
    assert manager.get_zoom("192.0.2.2") == 25


@pytest.mark.parametrize("kind", ["zoom", "ae"])
def test_return_to_busy_endpoint_waits_for_its_original_query(manager, kind):
    acquire = getattr(manager, f"{kind}_query_try_acquire")
    release = getattr(manager, f"{kind}_query_release")
    assert acquire("192.0.2.1")
    with patch("ptz.visca.manager.CameraWorker"):
        manager.update_camera_ip(1, "192.0.2.3")
        manager.update_camera_ip(1, "192.0.2.1")
    assert not acquire("192.0.2.1")
    release("192.0.2.1")
    assert acquire("192.0.2.1")


def test_retired_zoom_result_does_not_overwrite_new_endpoint(manager):
    with patch("ptz.visca.manager.CameraWorker"):
        manager.update_camera_ip(1, "192.0.2.3")
    manager.set_zoom("192.0.2.3", 12)
    manager.set_zoom("192.0.2.1", 78)
    assert manager.get_zoom("192.0.2.3") == 12


def test_same_ip_keeps_worker_connection_and_observations(manager):
    with patch('ptz.visca.manager.CameraWorker') as factory:
        original = Mock()
        manager._workers['192.0.2.1'] = original
        manager.set_zoom('192.0.2.1', 42)
        manager.update_camera_ip(1, '192.0.2.1')
        assert manager.worker('192.0.2.1') is original
        factory.assert_not_called()
        original.stop.assert_not_called()
        assert manager.get_zoom('192.0.2.1') == 42
