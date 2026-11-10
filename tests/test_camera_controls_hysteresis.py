"""Transport loss never removes session controls, even after old deadlines."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest


@pytest.fixture
def rig(monkeypatch):
    import ui.camera_controls_visibility as module
    class Timer:
        def __init__(self, parent):
            self.active = False
            self.timeout = SimpleNamespace(connect=lambda callback: setattr(self, 'callback', callback))
            self.starts = 0
        def setSingleShot(self, value):
            pass
        def stop(self):
            self.active = False
        def isActive(self):
            return self.active
        def start(self, duration):
            assert duration == 1800
            self.active = True
            self.starts += 1
        def fire(self):
            self.active = False
            self.callback()
    monkeypatch.setattr(module, 'QTimer', Timer)
    window = SimpleNamespace(session_active=True, _shutting_down=False,
        Cam1=SimpleNamespace(isChecked=lambda: True, _connected=True),
        Cam2=SimpleNamespace(_connected=False), _right_panel=Mock())
    controller = module.CameraControlsVisibility(window)
    return window, controller


def test_short_disconnect_keeps_controls_and_recovery_is_immediate(rig):
    window, controller = rig
    controller.update()
    window.Cam1._connected = False
    controller.update()
    window.Cam1._connected = True
    controller.update()
    assert all(call.args == (True,) for call in window._right_panel.show_camera_controls.call_args_list)
    assert not controller.timer.isActive()


def test_sustained_disconnect_keeps_panel_and_disables_motion(rig):
    window, controller = rig
    controller.update()
    window.Cam1._connected = False
    controller.update()
    controller.update()
    assert controller.timer.starts == 0
    assert controller.visible
    controller.timer.fire()
    assert controller.visible
    window._right_panel.set_camera_transport_state.assert_called_with(False)
    window.Cam1._connected = True
    controller.update()
    assert controller.visible


@pytest.mark.parametrize('action', ['session_end', 'shutdown', 'offline_selection'])
def test_only_session_end_or_shutdown_hides_controls(rig, action):
    window, controller = rig
    controller.update()
    window.Cam1._connected = False
    controller.update()
    if action == 'session_end':
        window.session_active = False
    elif action == 'shutdown':
        window._shutting_down = True
    else:
        window.Cam1.isChecked = lambda: False
    controller.update()
    assert controller.visible == (action == 'offline_selection')
    assert not controller.timer.isActive()


def test_startup_offline_shows_disabled_controls(rig):
    window, controller = rig
    window.Cam1._connected = False
    controller.update()
    assert controller.visible
    window._right_panel.set_camera_transport_state.assert_called_with(False)
    assert not controller.timer.isActive()


def test_main_window_route_does_not_hide_on_disconnect_blip(rig):
    from conftest import ensure_real_qt
    ensure_real_qt()
    from ui.main_window import MainWindow
    window, _ = rig
    MainWindow._update_controls_visibility(window)
    window.Cam1._connected = False
    MainWindow._update_controls_visibility(window)
    window.Cam1._connected = True
    MainWindow._update_controls_visibility(window)
    assert all(call.args == (True,) for call in window._right_panel.show_camera_controls.call_args_list)
