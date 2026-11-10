"""Loopback camera: slow Completion, ACK-only and silent link loss.

A silent peer holds TCP open (no FIN/RST) but drops replies. This models what
an unplugged network looks like to the client until its response deadline.
"""
import socket
import threading
import time
from types import SimpleNamespace

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.worker import CameraWorker


@pytest.mark.parametrize('reply', ['late_completion', 'ack_only', 'silent_drop'])
def test_adapter_never_reports_unconfirmed_camera_success(reply):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(3)
    received = threading.Event()
    release = threading.Event()
    failures = []

    def camera():
        try:
            with listener.accept()[0] as connection:
                connection.settimeout(3)
                assert connection.recv(64) == bytes.fromhex('8101043802ff')
                received.set()
                if reply != 'silent_drop':
                    connection.sendall(bytes.fromhex('9041ff'))
                if reply == 'late_completion':
                    # Deliberately exceeds the product's 1s read budget.
                    if not release.wait(1.25):
                        try:
                            connection.sendall(bytes.fromhex('9051ff'))
                        except OSError:
                            pass  # client correctly retired ambiguous session
                release.wait(4)
        except Exception as exc:
            failures.append(exc)

    server = threading.Thread(target=camera)
    server.start()
    worker = CameraWorker('127.0.0.1', listener.getsockname()[1])
    manager = SimpleNamespace(worker=lambda ip: worker)
    adapter = ViscaCameraAdapter(manager, {1: ('127.0.0.1', '81')})
    started = time.monotonic()
    try:
        result = adapter.focus_auto('cam1')
        elapsed = time.monotonic() - started
        assert received.is_set()
        assert not result.ok
        assert result.error_code == 'CAMERA_ERROR'
        assert 0.8 <= elapsed < 3
        # Failure must retire the connection so late data cannot confirm next call.
        assert worker._sock is None
    finally:
        # Give the delayed sender its actual >1s deadline before cleanup.
        if reply == 'late_completion':
            time.sleep(max(0, 1.35 - (time.monotonic() - started)))
        release.set()
        worker.stop()
        listener.close()
        server.join(5)
    assert not server.is_alive()
    assert not failures
