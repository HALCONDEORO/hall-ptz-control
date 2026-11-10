"""A late STOP observer notification must not cross a bus shutdown boundary."""
import threading

from core.events import AsyncEventBus, EventType


def test_late_stop_handler_does_not_replay_observers_after_restart(monkeypatch):
    bus = AsyncEventBus()
    entered, release = threading.Event(), threading.Event()
    observed = []

    def stop(event):
        entered.set()
        assert release.wait(2)

    bus.register_motion_safety(lambda event: event.payload.get('camera'), stop)
    bus.subscribe(EventType.CAMERA_STOP, lambda event: observed.append(event.payload['camera']))
    bus.start()
    bus.emit(EventType.CAMERA_STOP, camera=1)
    assert entered.wait(2)
    ordinary, emergency = bus._worker, bus._emergency_worker
    # Exercise the documented join-timeout path without a wall-clock delay.
    monkeypatch.setattr(emergency, 'join', lambda timeout=None: None)
    try:
        bus.stop()
        assert not ordinary.is_alive()
    finally:
        release.set()
        threading.Thread.join(emergency, timeout=2)
    assert not emergency.is_alive()
    bus.start()
    try:
        finished = threading.Event()
        bus.subscribe(EventType.SESSION_END, lambda event: finished.set())
        bus.emit(EventType.SESSION_END)
        assert finished.wait(2)
        assert observed == []
    finally:
        bus.stop()
