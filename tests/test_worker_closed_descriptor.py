# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""A local reconnect racing select must not kill the camera worker."""
import queue
import threading
from unittest.mock import Mock

from ptz.visca.worker import CameraWorker, ViscaCommand


def test_closed_descriptor_enters_normal_retry_and_does_not_kill_worker(monkeypatch):
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = "192.0.2.1"
    worker._interrupt = threading.Event()
    worker._shutdown = threading.Event()
    worker._lock = threading.Lock()
    worker._queue = queue.Queue()
    worker._sock = old = Mock()
    worker._is_connected = True
    worker.signals = Mock()
    worker._consecutive_no_response = 0
    fresh = Mock()
    fresh.recv.return_value = bytes.fromhex("9050ff")
    worker._connect_with_retry = Mock(return_value=fresh)
    def select(read, write, errors, timeout):
        if read == [old]:
            raise ValueError("file descriptor cannot be a negative integer (-1)")
        return [fresh], [], []
    monkeypatch.setattr("ptz.visca.worker.select.select", select)
    success, failure = Mock(), Mock()
    worker._queue.put(ViscaCommand(
        camera=1, payload=bytes.fromhex("8101040002ff"), fast_connect=True,
        on_success=success, on_failure=failure))
    worker._queue.put(None)
    worker._run()
    old.close.assert_called_once_with()
    fresh.sendall.assert_called_once_with(bytes.fromhex("8101040002ff"))
    success.assert_called_once_with()
    failure.assert_not_called()


def test_real_closed_socket_is_normalized_as_io_failure():
    import errno
    import socket
    import pytest

    worker = CameraWorker.__new__(CameraWorker)
    worker._interrupt = threading.Event()
    worker._shutdown = threading.Event()
    sock = socket.socket()
    sock.close()
    with pytest.raises(OSError) as error:
        worker._read_visca_response(sock)
    assert error.value.errno == errno.EBADF
