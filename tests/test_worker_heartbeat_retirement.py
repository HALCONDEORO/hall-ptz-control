"""An old heartbeat observation cannot resurrect retired connection state."""
import threading
from unittest.mock import Mock
import pytest
from ptz.visca.worker import CameraWorker


@pytest.mark.parametrize('retire', ['reconnect', 'stop'])
def test_heartbeat_alive_snapshot_cannot_overwrite_socket_retirement(retire):
    worker = object.__new__(CameraWorker)
    worker._lock = threading.Lock()
    worker._shutdown = threading.Event()
    worker._sock = Mock()
    worker._is_connected = True
    worker._set_connected = lambda value: setattr(worker, '_is_connected', value)
    entered, release = threading.Event(), threading.Event()
    def alive(_sock):
        entered.set()
        assert release.wait(2)
        return True  # Probe completed immediately before retirement.
    worker._socket_alive = alive
    ping = threading.Thread(target=worker._ping)
    ping.start()
    try:
        assert entered.wait(2)
        if retire == 'stop':
            worker._shutdown.set()
        worker._close_socket()
        assert worker.is_connected is False
        release.set()
        ping.join(2)
        assert not ping.is_alive()
        assert worker._sock is None
        assert worker.is_connected is False
    finally:
        release.set()
        ping.join(2)
