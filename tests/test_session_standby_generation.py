"""A retired standby must not run after a replacement session powers cameras."""
import threading
from types import SimpleNamespace

from application.session_service import SessionService


def test_restart_cancels_old_standby_and_orders_inflight_command(monkeypatch):
    monkeypatch.setattr('application.session_service.mark_session_active', lambda: None)
    monkeypatch.setattr('application.session_service.clear_session_marker', lambda: None)
    entered, release = threading.Event(), threading.Event()
    calls = []

    def standby(camera):
        calls.append(('standby', camera))
        if camera == 'cam1':
            entered.set()
            assert release.wait(3)
        return SimpleNamespace(ok=True)

    def power(camera):
        calls.append(('power_on', camera))
        return SimpleNamespace(ok=True)

    service = SessionService(SimpleNamespace(standby=standby, power_on=power,
                                             cancel_polls=lambda camera: None))
    try:
        service.end()
        assert entered.wait(3)
        service.start()  # never wait for hardware on the calling/Qt thread
        release.set()
        service._standby_thread.join(3)
        service._power_thread.join(3)
        assert not service._standby_thread.is_alive()
        assert not service._power_thread.is_alive()
        assert service.active
        assert calls == [('standby', 'cam1'), ('power_on', 'cam1'), ('power_on', 'cam2')]
    finally:
        release.set()
