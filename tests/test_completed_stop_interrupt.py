"""Synthetic worker loop tests. No transport thread or live socket is started."""
import queue
import threading
from unittest.mock import Mock

from ptz.visca.worker import CameraWorker, ViscaCommand


def _worker():
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._queue = queue.Queue(maxsize=20)
    worker._shutdown = threading.Event()
    worker._interrupt = threading.Event()
    worker._lock = threading.Lock()
    worker._sock = Mock()
    worker._set_connected = Mock()
    worker._close_socket = Mock()
    worker._consecutive_no_response = 0
    return worker


def test_completed_stop_is_not_replayed_or_disconnected_by_second_stop_frame():
    worker = _worker()
    pan = ViscaCommand(camera=1, payload=bytes.fromhex('8101060100000303ff'), priority=True)
    zoom = ViscaCommand(camera=1, payload=bytes.fromhex('8101040700ff'))
    sent = []
    pan.on_success = Mock()
    worker._sock.sendall.side_effect = lambda payload: sent.append(payload)

    def read(sock):
        if len(sent) == 1:
            worker.send_priority(zoom)
        else:
            worker._queue.put(None)
        return bytes.fromhex('9051ff')

    worker._read_visca_response = read
    worker._queue.put(pan)
    worker._run()
    assert sent == [pan.payload, zoom.payload]
    worker._close_socket.assert_not_called()
    pan.on_success.assert_called_once()
    assert worker._queue.empty()


def test_incomplete_stop_still_discards_ambiguous_connection():
    worker = _worker()
    pan = ViscaCommand(camera=1, payload=bytes.fromhex('8101060100000303ff'), priority=True)
    zoom = ViscaCommand(camera=1, payload=bytes.fromhex('8101040700ff'))
    sent = []
    worker._sock.sendall.side_effect = lambda payload: sent.append(payload)

    def read(sock):
        if len(sent) == 1:
            worker.send_priority(zoom)
            return bytes.fromhex('9041ff')
        worker._queue.put(None)
        return bytes.fromhex('9051ff')

    worker._read_visca_response = read
    worker._queue.put(pan)
    worker._run()
    worker._close_socket.assert_called_once()


def test_interrupted_stop_error_frame_still_fails_validation():
    worker = _worker()
    pan = ViscaCommand(camera=1, payload=bytes.fromhex('8101060100000303ff'), priority=True)
    zoom = ViscaCommand(camera=1, payload=bytes.fromhex('8101040700ff'))
    pan.on_success = Mock()
    pan.on_failure = Mock()
    worker.signals = Mock()
    sent = []
    worker._sock.sendall.side_effect = lambda payload: sent.append(payload)

    def read(sock):
        if len(sent) == 1:
            worker.send_priority(zoom)
            return bytes.fromhex('906102ff')
        worker._queue.put(None)
        return bytes.fromhex('9051ff')

    worker._read_visca_response = read
    worker._queue.put(pan)
    worker._run()
    pan.on_success.assert_not_called()
    pan.on_failure.assert_called_once()
    worker._close_socket.assert_called_once()


def test_interrupted_non_stop_completion_keeps_existing_cancellation():
    worker = _worker()
    move = ViscaCommand(camera=1, payload=bytes.fromhex('8101060101010202ff'))
    stop = ViscaCommand(camera=1, payload=bytes.fromhex('8101060100000303ff'))
    move.on_success = Mock()
    move.on_failure = Mock()
    sent = []
    worker._sock.sendall.side_effect = lambda payload: sent.append(payload)

    def read(sock):
        if len(sent) == 1:
            worker.send_priority(stop)
        else:
            worker._queue.put(None)
        return bytes.fromhex('9051ff')

    worker._read_visca_response = read
    worker._queue.put(move)
    worker._run()
    move.on_success.assert_not_called()
    move.on_failure.assert_called_once()
    worker._close_socket.assert_called_once()
