"""Confirmed mechanical commands retain their fixed caller deadline after ACK."""
import queue
import threading
from unittest.mock import Mock

from ptz.visca.worker import CameraWorker, ViscaCommand


def test_ack_then_completion_within_confirmed_deadline_is_not_early_failure(monkeypatch):
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
    arrivals = [(100.01, bytes.fromhex('9041ff')),
                (101.30, bytes.fromhex('9051ff'))]
    ready = []

    def poll(readers, writers, errors, timeout):
        limit = clock[0] + timeout
        if arrivals and arrivals[0][0] <= limit:
            at, frame = arrivals.pop(0)
            clock[0] = at
            ready.append(frame)
            return [sock], [], []
        clock[0] = limit
        return [], [], []

    monkeypatch.setattr('ptz.visca.worker.select.select', poll)
    sock.recv.side_effect = lambda size: ready.pop(0)
    success, failure = Mock(), Mock()
    cmd = ViscaCommand(camera=1, payload=bytes.fromhex('8101043f0201ff'),
                       fast_connect=True, expires_at=106.0, queued_at=100.0,
                       on_success=success, on_failure=failure)
    worker._queue.put(cmd)
    worker._queue.put(None)
    worker._run()
    success.assert_called_once()
    failure.assert_not_called()
    assert cmd.response == bytes.fromhex('9041ff9051ff')
    assert worker._consecutive_no_response == 0


import pytest


@pytest.mark.parametrize('body,priority,expected', [
    ('01043f0201', False, True),  # preset recall
    ('01044700000001', False, True),  # absolute zoom
    ('010604', False, True),  # only if a caller explicitly confirms Home
    ('01043f0201', True, False),
    ('01060105040103', False, False),
    ('01040723', False, False),
    ('01060100000303', True, False),
    ('01040700', True, False),
    ('090447', False, False),
    ('01040002', False, False),
])
def test_only_confirmed_mechanical_commands_extend_after_ack(monkeypatch, body, priority, expected):
    w, cmd, success, failure, clock = _scenario(monkeypatch, body, priority=priority)
    assert bool(success.call_count) is expected
    assert bool(failure.call_count) is not expected
    assert clock[0] == pytest.approx(101.3 if expected else 101.0)


def _scenario(monkeypatch, body='01043f0201', *, priority=False, ack=True,
              terminal_at=101.3, terminal='9051ff', interrupt_at=None,
              cancel_at=None, repeat_ack=False, deadline=106.0, fast=True):
    clock = [100.0]
    monkeypatch.setattr('ptz.visca.worker.time.monotonic', lambda: clock[0])
    w = CameraWorker.__new__(CameraWorker)
    w.ip = '192.0.2.1'
    w._interrupt, w._shutdown = threading.Event(), threading.Event()
    w._lock = threading.Lock()
    w._queue = queue.Queue()
    w._is_connected = True
    w.signals = Mock()
    w._consecutive_no_response = 0
    sock = w._sock = Mock()
    arrivals = ([(100.01, bytes.fromhex('9041ff'))] if ack else [])
    if repeat_ack:
        arrivals += [(100.8, bytes.fromhex('9041ff')), (101.8, bytes.fromhex('9041ff'))]
    arrivals += [(terminal_at, bytes.fromhex(terminal))]
    arrivals.sort()
    ready = []
    success, failure = Mock(), Mock()
    cmd = ViscaCommand(camera=1, payload=bytes.fromhex('81' + body + 'ff'),
                       priority=priority, fast_connect=fast, expires_at=deadline,
                       queued_at=100.0, on_success=success, on_failure=failure)

    def poll(readers, writers, errors, timeout):
        limit = clock[0] + timeout
        if arrivals and arrivals[0][0] <= limit:
            clock[0], frame = arrivals.pop(0)
            ready.append(frame)
            readable = [sock]
        else:
            clock[0] = limit
            readable = []
        if interrupt_at is not None and clock[0] >= interrupt_at:
            w._interrupt.set()
        if cancel_at is not None and clock[0] >= cancel_at:
            cmd.cancelled.set()
        return readable, [], []

    monkeypatch.setattr('ptz.visca.worker.select.select', poll)
    sock.recv.side_effect = lambda size: ready.pop(0)
    # Avoid reprocessing a deliberately interrupted STOP in this unit scenario.
    w._requeue = Mock()
    w._queue.put(cmd)
    w._queue.put(None)
    w._run()
    return w, cmd, success, failure, clock


def test_no_ack_keeps_original_one_second_read(monkeypatch):
    w, cmd, success, failure, clock = _scenario(monkeypatch, ack=False)
    success.assert_not_called()
    failure.assert_called_once()
    assert clock[0] == pytest.approx(101.0)
    assert w._sock is None


def test_ack_repetition_never_renews_absolute_deadline(monkeypatch):
    w, cmd, success, failure, clock = _scenario(
        monkeypatch, repeat_ack=True, deadline=102.0, terminal_at=102.3)
    success.assert_not_called()
    failure.assert_called_once()
    assert clock[0] == pytest.approx(102.0)
    assert w._sock is None


@pytest.mark.parametrize('control', ['interrupt_at', 'cancel_at'])
def test_stop_or_cancellation_aborts_extended_read_within_poll_slice(monkeypatch, control):
    w, cmd, success, failure, clock = _scenario(monkeypatch, **{control: 100.2})
    success.assert_not_called()
    assert clock[0] <= 100.26
    assert w._sock is None


def test_error_after_ack_is_failure_and_retires_socket(monkeypatch):
    w, cmd, success, failure, clock = _scenario(monkeypatch, terminal='906141ff')
    success.assert_not_called()
    failure.assert_called_once()
    assert w._sock is None
