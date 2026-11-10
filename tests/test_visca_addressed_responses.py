"""Addressed VISCA replies must retain framing, errors and socket correlation."""
import threading
from unittest.mock import patch

import pytest

from ptz.visca import parser


@pytest.mark.parametrize('header', range(0x90, 0xF1, 0x10))
def test_addressed_completion_and_inquiries(header):
    frame = bytes([header, 0x50, 0, 0, 0, 0, 0xFF])
    assert parser.contains_final_response(frame)
    assert parser.validate_visca_response(frame) == (True, '')
    assert parser.zoom(frame) == 0
    assert parser.exp_comp_level(frame) == -7
    assert parser.ae_mode(bytes([header, 0x50, 0, 0xFF])) == 'auto'
    assert parser.ptz_position(bytes([header, 0x50] + [0] * 8 + [0xFF])) == (0, 0)


@pytest.mark.parametrize('header', [0x00, 0x80, 0x81, 0x88, 0x91, 0x9F, 0xA1, 0xFF])
def test_non_response_addresses_stay_invalid(header):
    frame = bytes([header, 0x51, 0xFF])
    assert not parser.contains_final_response(frame)
    assert not parser.validate_visca_response(frame)[0]


def test_addressed_ack_error_and_truncation():
    assert not parser.contains_final_response(bytes.fromhex('a041ff'))
    assert not parser.contains_final_response(bytes.fromhex('a051'))
    assert not parser.contains_final_response(bytes.fromhex('a061ff'))
    error = bytes.fromhex('a041ffa06141ff')
    assert parser.contains_final_response(error)
    assert not parser.validate_visca_response(error)[0]


def test_worker_reads_fragmented_addressed_completion_and_filters_wrong_socket():
    from ptz.visca.worker import CameraWorker

    worker = object.__new__(CameraWorker)
    worker.ip = '192.0.2.2'
    worker._interrupt = threading.Event()
    worker._shutdown = threading.Event()
    worker._response_headers = {0x90, 0xA0}
    chunks = iter([bytes.fromhex('b050ff'), bytes.fromhex('a041ff'),
                   bytes.fromhex('a052ff'), bytes.fromhex('a0'), bytes.fromhex('51ff')])

    class Socket:
        def recv(self, size):
            return next(chunks, b'')

    sock = Socket()
    with patch('ptz.visca.worker.select.select', return_value=([sock], [], [])):
        assert worker._read_visca_response(sock) == bytes.fromhex('a041ffa051ff')


def test_worker_preserves_addressed_socket_zero_error():
    from ptz.visca.worker import CameraWorker

    worker = object.__new__(CameraWorker)
    worker.ip = '192.0.2.2'
    worker._response_headers = {0x90, 0xA0}
    ack = (0xA0, 1)
    assert worker._correlate_response_frame(bytes.fromhex('a06002'), ack) == (True, ack)
    assert worker._correlate_response_frame(bytes.fromhex('b06002'), ack) == (False, ack)
