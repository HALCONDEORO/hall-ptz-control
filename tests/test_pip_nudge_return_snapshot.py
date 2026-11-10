"""An active PiP return uses the outbound settings, not live UI edits."""
from unittest.mock import Mock, call, patch

import pytest

from application.pip_nudge_service import PiPNudgeService
from config.settings import PiPNudgeSettings


@pytest.mark.parametrize('speed,direction,duration', [
    (3, 'left', 100), (8, 'right', 500), (0, 'left', 0),
])
def test_live_settings_do_not_change_active_return(speed, direction, duration):
    port = Mock()
    service = PiPNudgeService(port, 'cam1', PiPNudgeSettings(
        pan_speed=3, direction='right', duration_ms=100))
    with patch('application.pip_nudge_service.threading.Timer') as timer:
        service.on_pip_on()
        service.update(speed, direction, duration)
        service.on_pip_off()
        assert port.move.call_args_list == [call('cam1', 3, 0), call('cam1', -3, 0)]
        assert timer.call_args.args[0] == 0.1
        service.on_pip_on()
        if speed and duration:
            expected = -speed if direction == 'left' else speed
            assert port.move.call_args_list[-1] == call('cam1', expected, 0)
            assert timer.call_args.args[0] == duration / 1000
        else:
            assert port.move.call_count == 2
        service.cancel()
        port.reset_mock()
        service.on_pip_off()
        port.move.assert_not_called()
