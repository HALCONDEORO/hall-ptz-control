"""STOP subscribers observe admitted/coalesced work, not every emit call."""
import threading

from core.events import AsyncEventBus, EventType


def test_pending_stop_coalesces_per_endpoint_for_serial_observers():
    bus = AsyncEventBus()
    entered, release, last_admitted = (threading.Event() for _ in range(3))
    admitted, observed = [], []
    observed_last = threading.Event()

    def prepare(event):
        return event.payload['endpoint']

    def admit(event):
        sequence = event.payload['sequence']
        admitted.append(sequence)
        if sequence == 1:
            entered.set()
            assert release.wait(2)
        if sequence == 3:
            last_admitted.set()

    bus.register_motion_safety(prepare, admit)
    def observe(event):
        observed.append(event.payload['sequence'])
        if event.payload['sequence'] == 3:
            observed_last.set()

    bus.subscribe(EventType.CAMERA_STOP, observe)
    bus.start()
    try:
        bus.emit(EventType.CAMERA_STOP, endpoint='synthetic', sequence=1)
        assert entered.wait(2)
        bus.emit(EventType.CAMERA_STOP, endpoint='synthetic', sequence=2)
        bus.emit(EventType.CAMERA_STOP, endpoint='synthetic', sequence=3)
        release.set()
        assert last_admitted.wait(2)
        assert observed_last.wait(2)
        assert admitted == [1, 3]
        assert observed == [1, 3]
    finally:
        release.set()
        bus.stop()
