# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Shutdown cannot rely on a sentinel being admitted to a full queue."""
import queue
import threading
from unittest.mock import Mock

from ptz.visca.worker import CameraWorker, ViscaCommand


def test_shutdown_exits_even_when_full_queue_rejects_sentinel():
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = "192.0.2.1"
    worker._shutdown = threading.Event()
    worker._interrupt = threading.Event()
    worker._lock = threading.Lock()
    worker._queue = queue.Queue(maxsize=1)
    worker._queue.put_nowait(ViscaCommand(1, bytes.fromhex("8101060101010101ff")))
    worker._sock = None
    worker.signals = Mock()
    worker._is_connected = False
    worker._connection_state = None
    # The full queue makes stop()'s sentinel insertion fail. An idle ping
    # breaks the loop only in the buggy version, so the test is deterministic
    # and never leaves a background thread behind.
    worker._queue.get = Mock(side_effect=[queue.Empty, RuntimeError("shutdown loop continued")])
    worker._ping = Mock()
    worker._shutdown.set()
    worker._interrupt.set()
    worker._run()
    worker._queue.get.assert_not_called()
    worker._ping.assert_not_called()


def test_stop_joins_real_worker_when_sentinel_admission_fails():
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = "192.0.2.1"
    worker._shutdown = threading.Event()
    worker._interrupt = threading.Event()
    worker._lock = threading.Lock()
    worker._queue = queue.Queue(maxsize=1)
    worker._sock = None
    worker.signals = Mock()
    worker._is_connected = False
    worker._connection_state = None
    worker._queue.put_nowait(ViscaCommand(1, bytes.fromhex("8101060101010101ff")))
    gate = threading.Event()
    real_put = worker._queue.put_nowait
    def full_sentinel(item):
        if item is None:
            gate.set()
            raise queue.Full
        return real_put(item)
    worker._queue.put_nowait = full_sentinel
    worker._thread = threading.Thread(target=lambda: (gate.wait(2), worker._run()), daemon=True)
    worker._thread.start()
    try:
        worker.stop()
        assert not worker._thread.is_alive()
    finally:
        gate.set()
        if worker._thread.is_alive():
            # Clean up the unfixed/base implementation, too.
            worker._queue.queue.clear()
            real_put(None)
            worker._thread.join(2)
