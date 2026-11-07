"""Regression probes for 68e8eb03. Expected to FAIL before fixes. No hardware."""
from threading import RLock
from unittest.mock import Mock, call, patch
from application.pip_nudge_service import PiPNudgeService
from config.settings import PiPNudgeSettings


def test_cancel_after_generation_check_does_not_stop_new_manual_move():
    port = Mock()
    service = PiPNudgeService(port, 'cam1', PiPNudgeSettings(
        pan_speed=3, direction='right', duration_ms=100))

    class InterleaveOnUnlock:
        def __init__(self):
            self.lock = RLock()
            self.armed = False

        def __enter__(self):
            self.lock.acquire()

        def __exit__(self, *args):
            self.lock.release()
            if self.armed:
                self.armed = False
                service.cancel()
                port.move('cam1', 7, 0)

    lock = InterleaveOnUnlock()
    service._lock = lock
    with patch('application.pip_nudge_service.threading.Timer'):
        service.on_pip_on()
        lock.armed = True
        service._stop_camera(service._generation)
    # A STOP before the manual move is safe; one after it is stale.
    calls = port.mock_calls
    assert calls[-1] == call.move('cam1', 7, 0), calls
