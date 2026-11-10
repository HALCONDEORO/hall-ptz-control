"""A producer paused before queue admission must observe terminal retirement."""
import queue
import threading
from unittest.mock import Mock

import pytest

from ptz.visca.worker import CameraWorker, ViscaCommand


@pytest.mark.parametrize('coalesce,priority', [(False, False), (True, False), (False, True)])
def test_stop_racing_with_admission_rejects_ordinary_command(monkeypatch, coalesce, priority):
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._queue = queue.Queue(maxsize=20)
    worker._shutdown, worker._interrupt = threading.Event(), threading.Event()
    worker._lock = threading.Lock()
    worker._sock = None
    worker._thread = Mock()
    worker._thread.is_alive.return_value = False
    worker._is_connected = False
    worker.signals = Mock()
    entered, release = threading.Event(), threading.Event()
    producer_thread = []

    def clock():
        if threading.current_thread() is producer_thread[0]:
            entered.set()
            assert release.wait(2)
        return 100.0

    monkeypatch.setattr('ptz.visca.worker.time.monotonic', clock)
    cmd = ViscaCommand(camera=1, payload=bytes.fromhex('81010604ff'),
                       coalesce=coalesce, priority=priority)
    accepted = []
    producer = threading.Thread(target=lambda: accepted.append(
        worker.send_priority(cmd) if priority else worker.send(cmd)))
    producer_thread.append(producer)
    producer.start()
    assert entered.wait(2)
    try:
        worker.stop()
    finally:
        release.set()
        producer.join(2)
    assert not producer.is_alive()
    assert accepted == [False]
    assert list(worker._queue.queue) == []


def test_shutdown_still_retains_emergency_stop_for_recovery():
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._queue = queue.Queue(maxsize=20)
    worker._shutdown, worker._interrupt = threading.Event(), threading.Event()
    worker._shutdown.set()
    stop = ViscaCommand(camera=1, payload=bytes.fromhex('8101040700ff'))
    assert worker.send_priority(stop) is True
    assert list(worker._queue.queue) == [stop]


def test_ordinary_admission_preserves_queue_task_accounting():
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._queue = queue.Queue(maxsize=20)
    worker._shutdown = threading.Event()
    cmd = ViscaCommand(camera=1, payload=bytes.fromhex('81090400ff'))
    assert worker.send(cmd)
    assert worker._queue.get_nowait() is cmd
    worker._queue.task_done()
    assert worker._queue.unfinished_tasks == 0
