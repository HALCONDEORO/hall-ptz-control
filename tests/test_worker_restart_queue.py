# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Restart must not replay movement from before a stalled session."""
import queue
import threading
from unittest.mock import Mock, patch

from ptz.visca.worker import CameraWorker, ViscaCommand

MOVE = bytes.fromhex("8101060101010101ff")
PT_STOP = bytes.fromhex("8101060100000303ff")
ZOOM_STOP = bytes.fromhex("8101040700ff")


def dormant_worker():
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = "documentation-camera"
    worker._thread = Mock()
    worker._thread.is_alive.return_value = False
    worker._lifecycle_lock = threading.Lock()
    worker._lock = threading.Lock()
    worker._sock = None
    worker._queue = queue.Queue(maxsize=20)
    worker._shutdown = threading.Event()
    worker._interrupt = threading.Event()
    worker._sentinel_pending = True
    worker._set_connected = Mock()
    return worker


def test_restart_drops_old_motion_and_completes_waiters_but_keeps_stops():
    worker = dormant_worker()
    stale = [ViscaCommand(1, MOVE, on_failure=Mock()),
             ViscaCommand(1, bytes.fromhex("81010604ff"), priority=True, on_failure=Mock())]
    stops = [ViscaCommand(1, PT_STOP, priority=True),
             ViscaCommand(1, ZOOM_STOP, priority=True)]
    for command in [stale[0], stops[0], None, stale[1], stops[1]]:
        worker._queue.put_nowait(command)
    with patch("ptz.visca.worker.threading.Thread"):
        assert worker.restart() is True
    assert list(worker._queue.queue) == stops
    assert worker._sentinel_pending is False
    for command in stale:
        assert command.cancelled.is_set()
        command.on_failure.assert_called_once_with()


def test_failure_callback_runs_outside_queue_mutex_and_cannot_block_other_failures():
    worker = dormant_worker()
    def failure():
        assert worker._queue.mutex.acquire(blocking=False)
        worker._queue.mutex.release()
        raise ValueError("test callback failure")
    first = ViscaCommand(1, MOVE, on_failure=failure)
    second = ViscaCommand(1, MOVE, on_failure=Mock())
    worker._queue.put_nowait(first)
    worker._queue.put_nowait(second)
    with patch("ptz.visca.worker.threading.Thread"):
        assert worker.restart() is True
    assert list(worker._queue.queue) == []
    second.on_failure.assert_called_once_with()
