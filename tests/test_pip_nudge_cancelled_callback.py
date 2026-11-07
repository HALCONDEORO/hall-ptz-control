"""Timer.cancel cannot retract a callback that already started."""
import threading
from unittest.mock import Mock, patch

from application.pip_nudge_service import PiPNudgeService
from config.settings import PiPNudgeSettings


def test_callback_waiting_on_lock_cannot_stop_manual_control_after_cancel():
    port = Mock()
    service = PiPNudgeService(port, 'cam1', PiPNudgeSettings(
        pan_speed=3, direction='right', duration_ms=100,
    ))
    with patch('application.pip_nudge_service.threading.Timer') as timer:
        service.on_pip_on()
        callback = timer.call_args.args[1]
        callback_args = timer.call_args.kwargs['args']
        entered = threading.Event()

        def expired_timer():
            entered.set()
            callback(*callback_args)

        # Let the expired callback start while cancel owns the same lock. The
        # Timer's cancel() cannot stop it now; the generation must reject it.
        with service._lock:
            thread = threading.Thread(target=expired_timer)
            thread.start()
            assert entered.wait(5)
            service.cancel()
            port.move('cam1', 7, 0)  # new manual movement
        thread.join(5)
        assert not thread.is_alive()
        timer.return_value.cancel.assert_called_once()
        port.stop_move.assert_not_called()
        assert service._pending_stop is None

        # Cancellation must not disable the stop for a later legitimate nudge.
        service.on_pip_on()
        new_callback = timer.call_args.args[1]
        new_callback(*timer.call_args.kwargs['args'])
        port.stop_move.assert_called_once_with('cam1')
