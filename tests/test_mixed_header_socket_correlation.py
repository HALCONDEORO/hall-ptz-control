"""Field bytes: direct-IP ACK and configured addressed terminal share socket."""
import threading
from unittest.mock import Mock, patch

import pytest

from ptz.visca.worker import CameraWorker
from ptz.visca.parser import validate_visca_response


def worker():
    result = CameraWorker.__new__(CameraWorker)
    result.ip = '192.0.2.2'
    result._interrupt = threading.Event()
    result._shutdown = threading.Event()
    # Exactly the set derived by _run for an outgoing 82 command.
    result._response_headers = {0x90, 0xA0}
    return result


@pytest.mark.parametrize('ack,terminal', [('9041ff', 'a051ff'), ('9042ff', 'a052ff')])
def test_field_mixed_header_completion_matches_configured_command_socket(ack, terminal):
    w = worker()
    sock = Mock()
    sock.recv.side_effect = [bytes.fromhex(ack), bytes.fromhex(terminal), b'']
    with patch('ptz.visca.worker.select.select', return_value=([sock], [], [])):
        response = w._read_visca_response(sock)
    assert response == bytes.fromhex(ack + terminal)
    assert validate_visca_response(response) == (True, '')


@pytest.mark.parametrize('frame', ['a052', 'b051', 'b06002'])
def test_wrong_socket_or_unconfigured_header_still_rejected(frame):
    w = worker()
    assert w._correlate_response_frame(bytes.fromhex(frame), (0x90, 1)) == (False, (0x90, 1))


def test_allowed_mixed_header_error_remains_failure():
    w = worker()
    assert w._correlate_response_frame(bytes.fromhex('a06141'), (0x90, 1)) == (True, (0x90, 1))
    assert not validate_visca_response(bytes.fromhex('9041ffa06141ff'))[0]


def test_cam1_does_not_accept_cam2_terminal():
    w = worker()
    w._response_headers = {0x90}
    assert w._correlate_response_frame(bytes.fromhex('a051'), (0x90, 1)) == (False, (0x90, 1))


def test_missing_command_allowlist_does_not_expand_header_identity():
    w = worker()
    del w._response_headers
    assert w._correlate_response_frame(bytes.fromhex('a051'), (0x90, 1)) == (False, (0x90, 1))


def test_ack_alone_is_still_not_success():
    assert not validate_visca_response(bytes.fromhex('9041ff'))[0]


def test_worker_derives_alias_headers_from_actual_82_command():
    import queue
    from ptz.visca.worker import ViscaCommand

    w = worker()
    del w._response_headers
    w._queue = queue.Queue()
    w._lock = threading.Lock()
    w._is_connected = True
    w.signals = Mock()
    w._consecutive_no_response = 0
    w._sock = Mock()
    w._sock.recv.side_effect = [bytes.fromhex('9042ff'), bytes.fromhex('a052ff'), b'']
    success, failure = Mock(), Mock()
    cmd = ViscaCommand(camera=2, payload=bytes.fromhex('8201043f0201ff'),
                       fast_connect=True, on_success=success, on_failure=failure)
    w._queue.put(cmd)
    w._queue.put(None)
    with patch('ptz.visca.worker.select.select', return_value=([w._sock], [], [])):
        w._run()
    success.assert_called_once()
    failure.assert_not_called()
    assert cmd.response == bytes.fromhex('9042ffa052ff')
    assert w._response_headers == {0x90, 0xA0}
    assert w._consecutive_no_response == 0
