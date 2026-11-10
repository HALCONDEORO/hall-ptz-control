"""Closing an old session cannot mark a newly published connection offline."""
import threading
from unittest.mock import Mock
from ptz.visca.worker import CameraWorker


def test_disconnect_state_is_published_before_releasing_socket_ownership():
    worker = object.__new__(CameraWorker)
    worker._lock = threading.Lock()
    worker._shutdown = threading.Event()
    old = Mock()
    worker._sock = old
    ownership_held = []
    def disconnected(value):
        assert value is False
        acquired = worker._lock.acquire(blocking=False)
        ownership_held.append(not acquired)
        if acquired:
            worker._lock.release()
    worker._set_connected = disconnected
    worker._close_socket()
    old.close.assert_called_once()
    assert worker._sock is None
    assert ownership_held == [True], 'A reconnect may publish between close and stale False'
