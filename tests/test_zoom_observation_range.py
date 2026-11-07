"""Invalid camera observations must not become plausible slider feedback."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca import parser
from ptz.visca.manager import CameraManager
from ptz.visca.types import ZOOM_MAX


def frame(raw):
    return bytes([0x90, 0x50, (raw >> 12) & 15, (raw >> 8) & 15,
                  (raw >> 4) & 15, raw & 15, 0xff])


@pytest.mark.parametrize('raw', [ZOOM_MAX + 1, 0x7fff, 0xffff])
def test_zoom_above_product_range_is_not_an_observation(raw):
    assert parser.zoom(frame(raw)) is None


def test_invalid_zoom_does_not_poison_cache_or_publish(monkeypatch):
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81'),
                                           2: ('192.0.2.2', '82')})
    worker = Mock()
    worker.send_inquiry.return_value = frame(0xffff)
    monkeypatch.setattr(manager, 'worker', Mock(return_value=worker))
    callbacks = []

    class InlineThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr('adapters.visca_camera_adapter.threading.Thread', InlineThread)
    adapter.refresh_zoom_display(1, callbacks.append)
    assert callbacks == []
    assert manager.get_zoom('192.0.2.1') is None
    # Invalid reads must still release the inflight guard.
    assert manager.zoom_query_try_acquire('192.0.2.1')
    manager.zoom_query_release('192.0.2.1')


@pytest.mark.parametrize('raw', [0, 1, ZOOM_MAX // 2, ZOOM_MAX])
def test_valid_boundary_zoom_observations_remain_accepted(raw):
    assert parser.zoom(frame(raw)) == raw
