"""Pending recall intents use the real serial bus and Controller, not a fake coordinator."""

import threading
from unittest.mock import Mock
from core.controller import Controller
from core.events import AsyncEventBus, EventType
from core.state import SystemState


def exercise(extra, expected, first_result=True):
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def recall(camera, preset):
        calls.append((camera, preset))
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
            return first_result
        return True

    state = SystemState()
    state.session.active = True
    bus = AsyncEventBus()
    port = Mock(recall_preset=recall)
    Controller(state, bus, Mock(), Mock(), port)
    bus.start()
    try:
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=1)
        assert entered.wait(2)
        extra(bus, state, port)
        assert calls == [("cam1", 1)]  # no interruption or parallel recall
        release.set()
        finished = threading.Event()
        bus.subscribe(EventType.CONNECTION_CHANGED, lambda event: finished.set())
        bus.emit(EventType.CONNECTION_CHANGED, camera=1, connected=True)
        assert finished.wait(3)
        assert calls == expected
        return state, port
    finally:
        release.set()
        bus.stop()


def test_last_pending_replaces_middle_with_real_controller():
    def pending(bus, *_):
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=2)
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=3)

    state, _ = exercise(pending, [("cam1", 1), ("cam1", 3)])
    assert state.camera(1).active_preset == 3


def test_pending_coalescing_is_per_camera():
    def pending(bus, *_):
        for cam, slot in [(1, 2), (2, 5), (1, 3), (2, 6)]:
            bus.emit(EventType.SEAT_SELECTED, camera=cam, preset=slot)

    state, _ = exercise(pending, [("cam1", 1), ("cam1", 3), ("cam2", 6)])
    assert state.camera(2).active_preset == 6


def test_default_camera_is_captured_at_emission_and_alias_preserved():
    def pending(bus, state, _):
        state.active_camera = 2
        bus.emit(EventType.SEAT_SELECTED, seat_number=5)
        bus.emit(EventType.SEAT_SELECTED, seat_number=6)
        state.active_camera = 1

    exercise(pending, [("cam1", 1), ("cam2", 6)])


def test_failed_inflight_does_not_discard_latest_pending():
    def pending(bus, *_):
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=2)
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=3)

    exercise(pending, [("cam1", 1), ("cam1", 3)], first_result=False)


def test_inactive_session_still_blocks_latest_pending():
    def pending(bus, state, _):
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=2)
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=3)
        state.session.active = False

    exercise(pending, [("cam1", 1)])


def test_stop_retires_old_pending_and_latest_pre_stop_together():
    def pending(bus, state, port):
        stopped = threading.Event()
        port.stop_move.side_effect = lambda *a, **k: stopped.set()
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=2)
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=3)
        bus.emit(EventType.CAMERA_STOP, camera=1)
        assert stopped.wait(2)

    state, _ = exercise(pending, [("cam1", 1)])
    assert state.camera(1).active_preset != 1


def test_session_events_remain_fifo_boundaries():
    seen = []
    entered = threading.Event()
    release = threading.Event()
    done = threading.Event()
    bus = AsyncEventBus()

    def recall(event):
        seen.append(event.payload["preset"])
        if event.payload["preset"] == 1:
            entered.set()
            assert release.wait(3)

    bus.subscribe(EventType.SEAT_SELECTED, recall)
    bus.subscribe(EventType.SESSION_END, lambda e: seen.append("end"))
    bus.subscribe(EventType.SESSION_START, lambda e: seen.append("start"))
    bus.subscribe(EventType.CONNECTION_CHANGED, lambda e: done.set())
    bus.start()
    try:
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=1)
        assert entered.wait(2)
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=2)
        bus.emit(EventType.SESSION_END)
        bus.emit(EventType.SESSION_START)
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=3)
        bus.emit(EventType.CONNECTION_CHANGED)
        release.set()
        assert done.wait(3)
        assert seen == [1, 2, "end", "start", 3]
    finally:
        release.set()
        bus.stop()


def test_ordinary_events_keep_order_and_payloads():
    seen = []
    done = threading.Event()
    bus = AsyncEventBus()
    bus.subscribe(EventType.SEAT_SELECTED, lambda e: seen.append(e.payload["preset"]))
    bus.subscribe(EventType.CAMERA_ZOOM, lambda e: seen.append(("zoom", e.payload["speed"])))
    bus.subscribe(EventType.CONNECTION_CHANGED, lambda e: done.set())
    # Buffered before first start: only the earlier preset intent is superseded.
    bus.emit(EventType.SEAT_SELECTED, camera=1, preset=1)
    bus.emit(EventType.CAMERA_ZOOM, camera=1, speed=2)
    bus.emit(EventType.SEAT_SELECTED, camera=1, preset=3)
    bus.emit(EventType.CONNECTION_CHANGED)
    bus.start()
    try:
        assert done.wait(2)
        assert seen == [("zoom", 2), 3]
        bus._queue.join()  # skipped entries must still balance task_done
    finally:
        bus.stop()


def test_shutdown_rejects_late_preset_and_restart_has_no_stale_intent():
    bus = AsyncEventBus()
    seen = []
    done = threading.Event()
    bus.subscribe(EventType.SEAT_SELECTED, lambda e: seen.append(e.payload["preset"]))
    bus.subscribe(EventType.CONNECTION_CHANGED, lambda e: done.set())
    bus.start()
    bus.stop()
    bus.emit(EventType.SEAT_SELECTED, camera=1, preset=9)
    bus.start()
    try:
        bus.emit(EventType.SEAT_SELECTED, camera=1, preset=3)
        bus.emit(EventType.CONNECTION_CHANGED)
        assert done.wait(2)
        assert seen == [3]
    finally:
        bus.stop()
