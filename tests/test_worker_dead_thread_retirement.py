"""Retirement owns transport cleanup even when the worker thread already died."""
import socket
from ptz.visca.worker import CameraWorker, ViscaCommand


def test_dead_worker_stop_closes_session_and_rejects_later_commands():
    local, peer = socket.socketpair()
    class ExitedWorker(CameraWorker):
        def _run(self):
            # Represents an unexpected worker exit with an established session.
            self._sock = local
            self._set_connected(True)
    worker = ExitedWorker('192.0.2.1')
    try:
        worker._thread.join(1)
        assert not worker._thread.is_alive()
        assert worker.is_connected
        worker.stop()
        assert worker._sock is None
        assert worker.is_connected is False
        assert worker._shutdown.is_set()
        assert worker.send(ViscaCommand(1, bytes.fromhex('81090400ff'))) is False
        peer.settimeout(0.2)
        assert peer.recv(1) == b''
        worker.stop()  # Idempotent even after transport retirement.
    finally:
        local.close()
        peer.close()
