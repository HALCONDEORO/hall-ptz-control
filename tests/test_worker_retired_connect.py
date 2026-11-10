"""A connection completing after retirement must never outlive its worker."""
import queue
import threading
from unittest.mock import Mock
import pytest
from ptz.visca.worker import CameraWorker


@pytest.mark.parametrize('path', ['ping', 'command'])
def test_stop_during_connect_closes_fresh_socket(path):
    from ptz.visca.worker import ViscaCommand
    worker = object.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._lock = threading.Lock()
    worker._shutdown = threading.Event()
    worker._interrupt = threading.Event()
    worker._sock = None
    worker._queue = queue.Queue()
    worker._is_connected = False
    worker._set_connected = lambda value: setattr(worker, '_is_connected', value)
    worker._set_state = Mock()
    entered, release = threading.Event(), threading.Event()
    fresh = Mock()
    def connect():
        entered.set()
        assert release.wait(2)
        worker._set_connected(True)
        return fresh
    worker._connect = connect
    if path == 'ping':
        worker._thread = threading.Thread(target=worker._ping)
    else:
        worker._queue.put(ViscaCommand(1, bytes.fromhex('81090400ff')))
        worker._thread = threading.Thread(target=worker._run)
    worker._thread.start()
    assert entered.wait(1)
    stopper = threading.Thread(target=worker.stop)
    stopper.start()
    assert worker._shutdown.wait(1)
    release.set()
    stopper.join(2)
    worker._thread.join(2)
    assert not worker._thread.is_alive()
    assert worker._sock is None
    assert worker.is_connected is False
    fresh.close.assert_called_once()


def test_shutdown_between_connect_return_and_publication_closes_socket():
    worker = object.__new__(CameraWorker)
    worker._lock = threading.Lock()
    worker._shutdown = threading.Event()
    worker._shutdown.set()
    worker._sock = None
    worker._set_connected = Mock()
    fresh = Mock()
    assert worker._publish_socket(fresh) is None
    fresh.close.assert_called_once()
    assert worker._sock is None
