# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Deterministic response-stream tests; no hardware or network connections."""
import queue
import threading
import time
from unittest.mock import Mock

import pytest

from ptz.visca.worker import CameraWorker, ViscaCommand


def bare_worker():
    w = CameraWorker.__new__(CameraWorker)
    w.ip = "192.0.2.1"
    w._interrupt = threading.Event()
    w._shutdown = threading.Event()
    w._lock = threading.Lock()
    w._queue = queue.Queue()
    w._sock = Mock()
    w._is_connected = True
    w.signals = Mock()
    w._consecutive_no_response = 0
    return w


@pytest.mark.parametrize("stale", [b"\x90\x52\xff", b"\x90\x62\x41\xff"])
def test_terminal_for_other_socket_does_not_finish_current_ack(monkeypatch, stale):
    w = bare_worker()
    chunks = [b"\x90\x41\xff" + stale, b"\x90\x51\xff"]
    w._sock.recv.side_effect = chunks
    monkeypatch.setattr("ptz.visca.worker.select.select", lambda *args: ([w._sock], [], []))
    response = w._read_visca_response(w._sock)
    assert response == b"\x90\x41\xff\x90\x51\xff"
    assert w._sock.recv.call_count == 2


def test_fragmented_matching_terminal_still_completes(monkeypatch):
    w = bare_worker()
    w._sock.recv.side_effect = [b"\x90\x41\xff\x90", b"\x51\xff"]
    monkeypatch.setattr("ptz.visca.worker.select.select", lambda *args: ([w._sock], [], []))
    assert w._read_visca_response(w._sock) == b"\x90\x41\xff\x90\x51\xff"


def test_completion_without_ack_remains_supported(monkeypatch):
    w = bare_worker()
    w._sock.recv.return_value = b"\x90\x50\xff"
    monkeypatch.setattr("ptz.visca.worker.select.select", lambda *args: ([w._sock], [], []))
    assert w._read_visca_response(w._sock) == b"\x90\x50\xff"


def run_one(w, response, *, expires_during_read=False):
    success, failure = Mock(), Mock()
    cmd = ViscaCommand(camera=1, payload=b"\x81\x01\x04\x00\x02\xff",
                       fast_connect=True, on_success=success, on_failure=failure)
    def read(sock):
        if expires_during_read:
            cmd.expires_at = time.monotonic() - 1
        return response
    w._read_visca_response = read
    w._queue.put(cmd)
    w._queue.put(None)
    w._run()
    return success, failure


def test_error_retires_session_before_next_command():
    w = bare_worker()
    sock = w._sock
    success, failure = run_one(w, b"\x90\x61\x41\xff")
    success.assert_not_called()
    failure.assert_called_once()
    sock.close.assert_called_once()
    assert w._sock is None


def test_completion_after_confirmed_deadline_is_failure_and_retires_session():
    w = bare_worker()
    sock = w._sock
    success, failure = run_one(w, b"\x90\x51\xff", expires_during_read=True)
    success.assert_not_called()
    failure.assert_called_once()
    sock.close.assert_called_once()


def test_socket_zero_rejection_after_ack_is_not_hidden(monkeypatch):
    w = bare_worker()
    w._sock.recv.return_value = b"\x90\x41\xff\x90\x60\x02\xff"
    monkeypatch.setattr("ptz.visca.worker.select.select", lambda *args: ([w._sock], [], []))
    assert w._read_visca_response(w._sock) == b"\x90\x41\xff\x90\x60\x02\xff"


def test_matching_error_wins_over_completion_in_same_chunk(monkeypatch):
    w = bare_worker()
    response = b"\x90\x41\xff\x90\x61\x41\xff\x90\x51\xff"
    w._sock.recv.return_value = response
    monkeypatch.setattr("ptz.visca.worker.select.select", lambda *args: ([w._sock], [], []))
    assert w._read_visca_response(w._sock) == response


def test_priority_interrupt_still_aborts_without_recv(monkeypatch):
    w = bare_worker()
    w._interrupt.set()
    poll = Mock()
    monkeypatch.setattr("ptz.visca.worker.select.select", poll)
    assert w._read_visca_response(w._sock) == b""
    poll.assert_not_called()
    w._sock.recv.assert_not_called()


def test_error_followed_by_partial_late_completion_cannot_confirm_next_command():
    w = bare_worker()
    old = w._sock
    fresh = Mock()
    w._connect_with_retry = Mock(return_value=fresh)
    successes, failures = Mock(), Mock()
    # The old session has an Error then a late Completion from its failed
    # command. A fresh session gives the second command its actual Error.
    old_responses = iter([b"\x90\x61\x41\xff\x90", b"\x90\x51\xff"])
    w._read_visca_response = lambda sock: (
        next(old_responses) if sock is old else b"\x90\x61\x41\xff"
    )
    for _ in range(2):
        w._queue.put(ViscaCommand(
            camera=1, payload=b"\x81\x01\x04\x00\x02\xff", fast_connect=True,
            on_success=successes, on_failure=failures,
        ))
    w._queue.put(None)
    w._run()
    successes.assert_not_called()
    assert failures.call_count == 2
    fresh.sendall.assert_called_once()
