"""Exercise the real MainWindow subscription without importing Qt."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest

from application.pip_nudge_service import PiPNudgeService
from config.settings import PiPNudgeSettings
from core.events import Event, EventType


def _handler(service, active_camera):
    from ui.pip_nudge_wiring import wire_pip_nudge_activity

    tree = ast.parse((Path(__file__).parents[1] / 'ui' / 'main_window.py').read_text())
    wiring_calls = [node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'wire_pip_nudge_activity']
    assert len(wiring_calls) == 1, 'MainWindow must wire PiP exactly once'
    assert any(isinstance(node, ast.ImportFrom) and node.module == 'ui.pip_nudge_wiring'
               and any(alias.name == 'wire_pip_nudge_activity' for alias in node.names)
               for node in ast.walk(tree))
    bus = Mock()
    window = SimpleNamespace(_pip_nudge_svc=service, _bus=bus,
                             _state=SimpleNamespace(active_camera=active_camera),
                             _record_activity=Mock(), _atem_dispatcher=Mock())
    compiled = compile(ast.Expression(wiring_calls[0]), '<real MainWindow wiring>', 'eval')
    eval(compiled, {'self': window, 'wire_pip_nudge_activity': wire_pip_nudge_activity})

    def dispatch(event):
        for registration in bus.subscribe.call_args_list:
            kind, callback = registration.args
            if kind == event.type:
                callback(event)
    return dispatch


@pytest.mark.parametrize('kind', [EventType.CAMERA_MOVE, EventType.SEAT_SELECTED])
@pytest.mark.parametrize('nudge_camera', [1, 2])
def test_other_camera_event_keeps_nudge_stop(kind, nudge_camera):
    port = Mock()
    camera_id = f'cam{nudge_camera}'
    service = PiPNudgeService(port, camera_id, PiPNudgeSettings(
        pan_speed=3, direction='right', duration_ms=100))
    handler = _handler(service, active_camera=nudge_camera)
    with patch('application.pip_nudge_service.threading.Timer') as timer:
        service.on_pip_on()
        args = timer.call_args.kwargs['args']
        handler(Event(kind, {'camera': 3 - nudge_camera}))
        timer.return_value.cancel.assert_not_called()
        service._stop_camera(*args)
    port.stop_move.assert_called_once_with(camera_id)


@pytest.mark.parametrize('kind,explicit', [
    (EventType.CAMERA_MOVE, True), (EventType.SEAT_SELECTED, True),
    (EventType.SEAT_SELECTED, False),
])
def test_target_camera_event_cancels_without_stopping_replacement(kind, explicit):
    port = Mock()
    service = PiPNudgeService(port, 'cam2', PiPNudgeSettings(
        pan_speed=3, direction='right', duration_ms=100))
    handler = _handler(service, active_camera=2)
    with patch('application.pip_nudge_service.threading.Timer') as timer:
        service.on_pip_on()
        args = timer.call_args.kwargs['args']
        handler(Event(kind, {'camera': 2} if explicit else {}))
        timer.return_value.cancel.assert_called_once()
        port.move('cam2', 7, 0)
        service._stop_camera(*args)
    port.stop_move.assert_not_called()
    assert port.move.call_args_list[-1] == call('cam2', 7, 0)


def test_implicit_seat_on_other_active_camera_keeps_stop():
    port = Mock()
    service = PiPNudgeService(port, 'cam1', PiPNudgeSettings(
        pan_speed=3, direction='right', duration_ms=100))
    with patch('application.pip_nudge_service.threading.Timer') as timer:
        service.on_pip_on()
        _handler(service, active_camera=2)(Event(EventType.SEAT_SELECTED, {}))
        timer.return_value.cancel.assert_not_called()
        service._stop_camera(*timer.call_args.kwargs['args'])
    port.stop_move.assert_called_once_with('cam1')


def test_zoom_activity_does_not_cancel_pan_stop():
    port = Mock()
    service = PiPNudgeService(port, 'cam1', PiPNudgeSettings(
        pan_speed=3, direction='right', duration_ms=100))
    handler = _handler(service, active_camera=1)
    with patch('application.pip_nudge_service.threading.Timer') as timer:
        service.on_pip_on()
        handler(Event(EventType.CAMERA_ZOOM, {'camera': 1, 'speed': 3}))
        timer.return_value.cancel.assert_not_called()
        service._stop_camera(*timer.call_args.kwargs['args'])
    port.stop_move.assert_called_once_with('cam1')
