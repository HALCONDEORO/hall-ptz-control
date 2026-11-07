"""Queued display updates must not apply after a camera was reconfigured."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.manager import CameraManager
from ui.display_freshness import capture_display_generation, display_update_is_current


@pytest.fixture
def adapter(monkeypatch):
    manager = CameraManager(SimpleNamespace(ip="192.0.2.1", cam_id="81"),
                            SimpleNamespace(ip="192.0.2.2", cam_id="82"))
    monkeypatch.setattr(manager, "worker", Mock())
    return ViscaCameraAdapter(manager, {1: ("192.0.2.1", "81"),
                                        2: ("192.0.2.2", "82")})


def test_generation_changes_on_every_reconfiguration(adapter):
    first = adapter.display_generation(1)
    adapter.update_camera_ip(1, "192.0.2.3")
    second = adapter.display_generation(1)
    adapter.update_camera_ip(1, "192.0.2.1")  # A -> B -> A must not look unchanged
    third = adapter.display_generation(1)
    assert len({first, second, third}) == 3
    assert adapter.display_generation(2) == 0  # other slot untouched


def test_generation_tracks_live_config_mode():
    manager = CameraManager(SimpleNamespace(ip="192.0.2.1", cam_id="81"),
                            SimpleNamespace(ip="192.0.2.2", cam_id="82"))
    live = ViscaCameraAdapter(manager, None)
    before = live.display_generation(1)
    live.update_camera_ip(1, "192.0.2.9")
    assert live.display_generation(1) != before


def test_queued_update_applies_when_nothing_changed(adapter):
    gen = capture_display_generation(adapter, 1)
    assert display_update_is_current(adapter, 1, gen, selected_cam_key=1)


@pytest.mark.parametrize("back_to_original", [False, True])
def test_queued_update_dropped_after_reconfiguration(adapter, back_to_original):
    gen = capture_display_generation(adapter, 1)  # ticket taken, event queued
    adapter.update_camera_ip(1, "192.0.2.3")
    if back_to_original:
        adapter.update_camera_ip(1, "192.0.2.1")
    assert not display_update_is_current(adapter, 1, gen, selected_cam_key=1)


def test_queued_update_dropped_when_other_camera_is_selected(adapter):
    gen = capture_display_generation(adapter, 1)
    assert not display_update_is_current(adapter, 1, gen, selected_cam_key=2)


def test_reconfiguring_other_camera_keeps_update(adapter):
    gen = capture_display_generation(adapter, 1)
    adapter.update_camera_ip(2, "192.0.2.4")
    assert display_update_is_current(adapter, 1, gen, selected_cam_key=1)


def test_port_without_generation_support_is_treated_as_unchanged():
    port = object()
    assert capture_display_generation(port, 1) == 0
    assert display_update_is_current(port, 1, 0, selected_cam_key=1)


def test_queued_update_dropped_after_session_poll_cancellation(adapter):
    gen = capture_display_generation(adapter, 1)
    adapter.cancel_polls("cam1")
    assert not display_update_is_current(adapter, 1, gen, selected_cam_key=1)
    new_gen = capture_display_generation(adapter, 1)
    assert display_update_is_current(adapter, 1, new_gen, selected_cam_key=1)
    assert adapter.display_generation(2) == 0
