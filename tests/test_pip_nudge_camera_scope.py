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
    tree = ast.parse((Path(__file__).parents[1] / 'ui' / 'main_window.py').read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Tuple):
            continue
        names = [elt.attr for elt in node.iter.elts if isinstance(elt, ast.Attribute)]
        if names != ['CAMERA_MOVE', 'SEAT_SELECTED']:
            continue
        expression = next(child for child in ast.walk(node) if isinstance(child, ast.Lambda))
        compiled = compile(ast.Expression(expression), '<real nudge subscription>', 'eval')
        window = SimpleNamespace(_pip_nudge_svc=service,
                                 _state=SimpleNamespace(active_camera=active_camera))
        return eval(compiled, {'self': window})
    raise AssertionError('PiP cancellation subscription missing')


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
