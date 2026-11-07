"""A TCP peer closing without a response is not a reachable VISCA camera."""
from unittest.mock import MagicMock, patch

import pytest

import config


@pytest.mark.parametrize('reply, expected', [(b'', False), (b'\x90\x50\x02\xff', True)])
def test_camera_probe_requires_response(reply, expected):
    sock = MagicMock()
    sock.recv.return_value = reply
    with patch('config.socket.socket') as factory:
        factory.return_value.__enter__.return_value = sock
        assert config.check_camera('192.0.2.10', '81') is expected
    sock.connect.assert_called_once_with(('192.0.2.10', config.VISCA_PORT))
    sock.sendall.assert_called_once_with(bytes.fromhex('81090400FF'))
    sock.recv.assert_called_once_with(1024)


@pytest.mark.parametrize('error', [TimeoutError('timed out'), ConnectionResetError('reset')])
def test_camera_probe_receive_failure_stays_unavailable(error):
    sock = MagicMock()
    sock.recv.side_effect = error
    with patch('config.socket.socket') as factory:
        factory.return_value.__enter__.return_value = sock
        assert config.check_camera('192.0.2.10', '81') is False
