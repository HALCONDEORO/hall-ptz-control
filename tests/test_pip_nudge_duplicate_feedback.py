"""Fresh monitors can report the same active PiP; this is not another edge."""
from unittest.mock import Mock, call, patch

from application.pip_nudge_service import PiPNudgeService
from config.settings import PiPNudgeSettings
from domain.atem_state import ATEMPiPState


def test_reconnect_on_snapshot_does_not_add_another_outbound_nudge():
    port = Mock()
    service = PiPNudgeService(port, 'cam1', PiPNudgeSettings(pan_speed=5, duration_ms=100))
    with patch('application.pip_nudge_service.threading.Timer'):
        service.on_pip_changed(ATEMPiPState(True, 2))
        service.on_pip_changed(ATEMPiPState(True, 2))
        service.on_pip_changed(ATEMPiPState(True, 3))
        service.on_pip_changed(ATEMPiPState(False, None))
        service.on_pip_changed(ATEMPiPState(False, None))
    assert port.move.call_args_list == [call('cam1', 5, 0), call('cam1', -5, 0)]


def test_new_on_after_off_still_nudges():
    port = Mock()
    service = PiPNudgeService(port, 'cam1', PiPNudgeSettings(pan_speed=5, duration_ms=100))
    with patch('application.pip_nudge_service.threading.Timer'):
        for enabled in [True, False, True, False]:
            service.on_pip_changed(ATEMPiPState(enabled, None))
    assert port.move.call_args_list == [call('cam1', 5, 0), call('cam1', -5, 0)] * 2


def test_duplicate_on_after_manual_cancel_does_not_restart_motion():
    port = Mock()
    service = PiPNudgeService(port, 'cam1', PiPNudgeSettings(pan_speed=5, duration_ms=100))
    with patch('application.pip_nudge_service.threading.Timer'):
        service.on_pip_changed(ATEMPiPState(True, 2))
        service.cancel()
        service.on_pip_changed(ATEMPiPState(True, 2))
        service.on_pip_changed(ATEMPiPState(False, None))
    port.move.assert_called_once_with('cam1', 5, 0)


def test_session_restart_resets_observed_state_through_real_wiring():
    from core.events import Event, EventType
    from ui.pip_nudge_wiring import wire_pip_nudge_activity
    from types import SimpleNamespace
    port, bus = Mock(), Mock()
    service = PiPNudgeService(port, 'cam1', PiPNudgeSettings(pan_speed=5, duration_ms=100))
    window = SimpleNamespace(_bus=bus, _pip_nudge_svc=service)
    wire_pip_nudge_activity(window)
    with patch('application.pip_nudge_service.threading.Timer'):
        service.on_pip_changed(ATEMPiPState(True, 2))
        for registration in bus.subscribe.call_args_list:
            kind, callback = registration.args
            if kind == EventType.SESSION_START:
                callback(Event(kind, {}))
        service.on_pip_changed(ATEMPiPState(True, 2))
    assert port.move.call_count == 2
