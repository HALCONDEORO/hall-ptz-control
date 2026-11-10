"""Malformed streams cannot grow the response buffer until the read deadline."""
import errno
import threading
from unittest.mock import Mock, patch
import pytest
from ptz.visca.worker import CameraWorker, MAX_VISCA_RESPONSE_BYTES


@pytest.mark.parametrize('chunk', [b'X' * 1024, b'\x90\x41\xff' * 300])
def test_unterminated_or_repeated_frames_hit_bounded_budget(chunk):
    worker = object.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._interrupt = threading.Event()
    worker._shutdown = threading.Event()
    worker._response_headers = {0x90}
    sock = Mock()
    sock.recv.return_value = chunk
    with patch('ptz.visca.worker.select.select', return_value=([sock], [], [])):
        with pytest.raises(OSError) as failure:
            worker._read_visca_response(sock)
    assert failure.value.errno == errno.EMSGSIZE
    assert sock.recv.call_count * len(chunk) <= MAX_VISCA_RESPONSE_BYTES + len(chunk)
