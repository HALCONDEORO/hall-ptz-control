"""A successful preset invalidates pending as well as cached zoom feedback."""
from types import SimpleNamespace
from unittest.mock import Mock

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.manager import CameraManager
from ui.display_freshness import capture_display_generation, display_update_is_current


def rig(monkeypatch):
    manager = CameraManager(SimpleNamespace(ip='192.0.2.1', cam_id='81'),
                            SimpleNamespace(ip='192.0.2.2', cam_id='82'))
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81'),
                                           2: ('192.0.2.2', '82')})
    monkeypatch.setattr(manager, 'worker', Mock())
    pending = []

    class DeferredThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            pending.append(self.target)

    monkeypatch.setattr('adapters.visca_camera_adapter.threading.Thread', DeferredThread)
    return adapter, manager, pending


def test_pre_preset_read_cannot_repopulate_invalidated_zoom(monkeypatch):
    adapter, manager, pending = rig(monkeypatch)
    feedback = Mock()

    def delayed_observation(*args):
        adapter.invalidate_zoom(1)  # Controller's successful-recall path
        return 8192  # observation captured before the preset moved zoom

    adapter._query_zoom = Mock(side_effect=delayed_observation)
    adapter.refresh_zoom_display(1, feedback)
    pending.pop(0)()
    feedback.assert_not_called()
    assert manager.get_zoom('192.0.2.1') is None


def test_pre_preset_queued_feedback_is_retired(monkeypatch):
    adapter, manager, pending = rig(monkeypatch)
    generation = capture_display_generation(adapter, 1)
    manager.set_zoom('192.0.2.1', 50)
    adapter.invalidate_zoom(1)
    assert not display_update_is_current(adapter, 1, generation, 1)
    assert manager.get_zoom('192.0.2.1') is None
    assert adapter.display_generation(2) == 0


def test_fresh_post_preset_read_works(monkeypatch):
    adapter, manager, pending = rig(monkeypatch)
    adapter.invalidate_zoom(1)
    adapter._query_zoom = Mock(return_value=4096)
    feedback = Mock()
    adapter.refresh_zoom_display(1, feedback)
    pending.pop(0)()
    feedback.assert_called_once_with(25)
    assert manager.get_zoom('192.0.2.1') == 25


def test_new_post_preset_read_is_not_lost_behind_old_inflight_query(monkeypatch):
    adapter, manager, pending = rig(monkeypatch)
    old, latest, superseded = Mock(), Mock(), Mock()
    adapter._query_zoom = Mock(return_value=4096)
    adapter.refresh_zoom_display(1, old)
    adapter.invalidate_zoom(1)
    adapter.refresh_zoom_display(1, superseded)
    adapter.refresh_zoom_display(1, latest)
    assert len(pending) == 1
    pending.pop(0)()
    old.assert_not_called()
    assert len(pending) == 1, 'Fresh readback was dropped behind retired query'
    pending.pop(0)()
    adapter._query_zoom.assert_called_once()
    superseded.assert_not_called()
    latest.assert_called_once_with(25)
    assert manager.get_zoom('192.0.2.1') == 25
    assert not pending


def test_session_cancellation_drops_coalesced_zoom_readback(monkeypatch):
    adapter, manager, pending = rig(monkeypatch)
    adapter._query_zoom = Mock(return_value=4096)
    old, latest = Mock(), Mock()
    adapter.refresh_zoom_display(1, old)
    adapter.invalidate_zoom(1)
    adapter.refresh_zoom_display(1, latest)
    adapter.cancel_polls('cam1')
    pending.pop(0)()
    old.assert_not_called()
    latest.assert_not_called()
    adapter._query_zoom.assert_not_called()
    assert not pending
    assert manager.get_zoom('192.0.2.1') is None
