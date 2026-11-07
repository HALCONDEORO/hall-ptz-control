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
