"""STOP tickets without a live consumer must reject, never wait forever."""
import threading
from unittest.mock import Mock

from adapters.visca_camera_adapter import ViscaCameraAdapter
from core.controller import Controller
from core.events import AsyncEventBus, EventType
from core.state import SystemState


def test_stop_emitted_after_shutdown_releases_waiter_but_does_not_admit_motion():
    bus = AsyncEventBus()
    manager = Mock()
    manager.worker.return_value.send.return_value = True
    manager.worker.return_value.send_priority.return_value = True
    port = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})
    state = SystemState()
    Controller(state, bus, Mock(), Mock(), port)
    bus.start()
    bus.stop()
    bus.emit(EventType.CAMERA_STOP, camera=1)
    done = threading.Event()
    result = []
    def move():
        result.append(port.move('cam1', 3, 0))
        done.set()
    thread = threading.Thread(target=move, daemon=True)
    thread.start()
    try:
        assert done.wait(0.5), 'movement waited forever on STOP with no consumer'
        assert result[0].ok is False
        manager.worker.return_value.send.assert_not_called()
    finally:
        # Release the baseline bug so the test leaves no live waiting thread.
        bus.start()
        bus.emit(EventType.CAMERA_STOP, camera=1)
        thread.join(1)
        bus.stop()


def test_cancelled_stop_requires_new_live_stop_before_fresh_motion():
    from core.motion_admission import MotionAdmission
    fence = MotionAdmission(lambda cid: cid)
    old = fence.capture('cam1')
    stop = fence.retire('cam1')
    sent = Mock(return_value=True)
    fence.cancel(stop)
    with fence.intent(old):
        assert fence.admit('cam1', sent) is False
    with fence.intent(fence.capture('cam1')):
        assert fence.admit('cam1', sent) is False
    sent.assert_not_called()
    renewed = fence.retire('cam1')
    assert fence.stop(renewed, lambda: True) is True
    with fence.intent(fence.capture('cam1')):
        assert fence.admit('cam1', sent) is True
    sent.assert_called_once()


def test_stop_cancels_inflight_and_pending_barriers_on_shutdown():
    from core.motion_admission import MotionAdmission
    fence = MotionAdmission(lambda cid: cid)
    bus = AsyncEventBus()
    entered, release = threading.Event(), threading.Event()
    def prepare(event):
        event.ticket = fence.retire(event.payload['camera'])
        return event.payload['camera']
    def stop(event):
        entered.set()
        release.wait(8)
    bus.register_motion_safety(prepare, stop, lambda event: fence.cancel(event.ticket))
    bus.start()
    bus.emit(EventType.CAMERA_STOP, camera='cam1')
    assert entered.wait(1)
    first = fence.capture('cam1')
    bus.emit(EventType.CAMERA_STOP, camera='cam2')
    second = fence.capture('cam2')
    stopper = threading.Thread(target=bus.stop)
    stopper.start()
    try:
        assert first.ready.wait(5)
        assert second.ready.wait(1)
        assert not fence.current(first)
        assert not fence.current(second)
    finally:
        release.set()
        stopper.join(3)
        bus.stop()
