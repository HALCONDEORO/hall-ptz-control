"""Empty VISCA reads must identify timeout versus remote EOF in diagnostics."""
import queue
import threading
from unittest.mock import Mock

import pytest

from ptz.visca.worker import CameraWorker, ViscaCommand


@pytest.mark.parametrize('peer_eof,reason', [(False, 'deadline'), (True, 'peer_eof')])
def test_empty_response_warning_identifies_read_end(monkeypatch, caplog, peer_eof, reason):
    clock = [100.0]
    monkeypatch.setattr('ptz.visca.worker.time.monotonic', lambda: clock[0])
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._interrupt = threading.Event()
    worker._shutdown = threading.Event()
    worker._lock = threading.Lock()
    worker._queue = queue.Queue()
    worker._is_connected = True
    worker.signals = Mock()
    worker._consecutive_no_response = 0
    sock = worker._sock = Mock()
    sock.recv.return_value = b''

    def poll(readers, writers, errors, timeout):
        clock[0] += timeout
        return ([sock] if peer_eof else []), [], []

    monkeypatch.setattr('ptz.visca.worker.select.select', poll)
    success, failure = Mock(), Mock()
    worker._queue.put(ViscaCommand(camera=1, payload=bytes.fromhex('8101043f0201ff'),
                                  fast_connect=True, queued_at=100.0,
                                  on_success=success, on_failure=failure))
    worker._queue.put(None)
    with caplog.at_level('WARNING', logger='ptz.visca.worker'):
        worker._run()
    warning = next(record.getMessage() for record in caplog.records
                   if 'no final VISCA frame' in record.getMessage())
    assert 'read_end=' + reason in warning
    assert 'empty' in warning
    success.assert_not_called()
    failure.assert_called_once()
    sock.close.assert_called_once()
    assert worker._sock is None
    if peer_eof:
        sock.recv.assert_called_once()
    else:
        sock.recv.assert_not_called()


@pytest.mark.parametrize('raw', [bytes.fromhex('b051ff'), bytes.fromhex('9051')])
def test_empty_accepted_buffer_does_not_claim_no_raw_bytes(monkeypatch, caplog, raw):
    clock = [100.0]
    monkeypatch.setattr('ptz.visca.worker.time.monotonic', lambda: clock[0])
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._interrupt = threading.Event()
    worker._shutdown = threading.Event()
    worker._lock = threading.Lock()
    worker._queue = queue.Queue()
    worker._is_connected = True
    worker.signals = Mock()
    worker._consecutive_no_response = 0
    sock = worker._sock = Mock()
    sock.recv.return_value = raw
    first = [True]

    def poll(readers, writers, errors, timeout):
        clock[0] += timeout
        if first[0]:
            first[0] = False
            return [sock], [], []
        return [], [], []

    monkeypatch.setattr('ptz.visca.worker.select.select', poll)
    worker._queue.put(ViscaCommand(camera=1, payload=bytes.fromhex('8101043f0201ff'),
                                  fast_connect=True, queued_at=100.0))
    worker._queue.put(None)
    with caplog.at_level('WARNING', logger='ptz.visca.worker'):
        worker._run()
    warning = next(record.getMessage() for record in caplog.records
                   if 'no final VISCA frame' in record.getMessage())
    assert '(0 bytes: empty)' in warning
    assert 'raw_received=' + str(len(raw)) in warning
    assert 'pending_bytes=' + str(0 if raw.endswith(b'\xff') else len(raw)) in warning
