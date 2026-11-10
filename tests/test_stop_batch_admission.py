"""Atomic STOP-pair admission using real queue methods, without sockets."""
import queue
import threading
from unittest.mock import Mock

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.worker import CameraWorker, ViscaCommand

PAN = bytes.fromhex('8101060100000303ff')
ZOOM = bytes.fromhex('8101040700ff')
MOVE = bytes.fromhex('8101060101010202ff')


def worker(size=20):
    w = CameraWorker.__new__(CameraWorker)
    w.ip = '192.0.2.1'
    w._queue = queue.Queue(maxsize=size)
    w._shutdown = threading.Event()
    w._interrupt = Mock(wraps=threading.Event())
    return w


def test_adapter_publishes_both_stop_frames_before_first_interrupt_is_consumed():
    w = worker()
    snapshots = []
    original = w._queue.not_empty.notify
    def notify(*args):
        snapshots.append([c.payload for c in w._queue.queue if c is not None])
        return original(*args)
    w._queue.not_empty.notify = notify
    manager = Mock()
    manager.worker.return_value = w
    adapter = ViscaCameraAdapter(manager, {1: ('192.0.2.1', '81')})
    assert adapter.stop_move('cam1').ok is True
    assert snapshots == [[PAN, ZOOM]]
    assert w._interrupt.set.call_count == 1
    assert [c.payload for c in w._queue.queue] == [PAN, ZOOM]
    assert all(c.priority for c in w._queue.queue)


def test_batch_drains_old_motion_and_defers_failure_callback():
    w = worker()
    failed = Mock()
    w._queue.put(ViscaCommand(camera=1, payload=MOVE, on_failure=failed))
    deferred = []
    assert w._send_stop_batch_admitted([
        ViscaCommand(camera=1, payload=PAN), ViscaCommand(camera=1, payload=ZOOM)
    ], deferred_failures=deferred) is True
    failed.assert_not_called()
    assert len(deferred) == 1
    deferred[0]()
    failed.assert_called_once()
    assert [c.payload for c in w._queue.queue] == [PAN, ZOOM]


def test_pair_rejection_never_publishes_half_or_discards_shutdown_sentinel():
    w = worker(size=2)
    w._queue.put(None)
    assert w._send_stop_batch_admitted([
        ViscaCommand(camera=1, payload=PAN), ViscaCommand(camera=1, payload=ZOOM)
    ]) is False
    assert list(w._queue.queue) == [None]
    w._interrupt.set.assert_not_called()


def test_repeated_pairs_replace_identical_pending_stops_without_growth():
    w = worker()
    for _ in range(3):
        assert w._send_stop_batch_admitted([
            ViscaCommand(camera=1, payload=PAN), ViscaCommand(camera=1, payload=ZOOM)
        ]) is True
    assert [c.payload for c in w._queue.queue] == [PAN, ZOOM]


def test_batch_rejects_motion_without_side_effects():
    w = worker()
    assert w._send_stop_batch_admitted([
        ViscaCommand(camera=1, payload=PAN), ViscaCommand(camera=1, payload=MOVE)
    ]) is False
    assert w._queue.empty()
    w._interrupt.set.assert_not_called()
