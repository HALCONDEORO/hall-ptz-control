"""Socket allocation failure uses bounded recovery instead of killing heartbeat."""
import errno
import threading
from unittest.mock import Mock, patch
import pytest
from domain.retry_policy import RetryPolicy
from ptz.visca.worker import CameraWorker


@pytest.mark.parametrize('error', [errno.EMFILE, errno.ENFILE, errno.ENOBUFS])
def test_socket_allocation_failure_returns_disconnected_and_can_recover(error):
    worker = object.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker.port = 5678
    worker._shutdown = threading.Event()
    worker._interrupt = threading.Event()
    worker._set_connected = Mock()
    worker._set_state = Mock()
    good = Mock()
    with patch('ptz.visca.worker.socket.socket', side_effect=[OSError(error, 'allocation failed'), good]) as factory:
        assert worker._connect_with_retry(RetryPolicy(backoffs=())) is None
        worker._set_connected.assert_called_with(False)
        # A later heartbeat can reconnect without spawning another worker.
        assert worker._connect_with_retry(RetryPolicy(backoffs=())) is good
        assert factory.call_count == 2
        good.close.assert_not_called()
