"""A dead established ATEM session retries instead of polling/logging forever."""
from types import SimpleNamespace
from unittest.mock import Mock

from adapters.atem_monitor import ATEMMonitor
from domain.atem_state import ATEMState
from domain.retry_policy import ATEM_RETRY_POLICY


def test_dead_session_reconnects_with_backoff_and_bounded_logs(monkeypatch):
    import adapters.atem_monitor as module
    monitor = ATEMMonitor('192.0.2.50')
    clients = []
    done = {'value': False}
    class Client:
        def __init__(self):
            self.number = len(clients)
            self.disconnect = Mock()
            clients.append(self)
        def connect(self, ip): pass
        def waitForConnection(self, timeout): return True
        @property
        def programInput(self):
            if self.number == 0:
                raise ConnectionError('session dead')
            done['value'] = True
            return [SimpleNamespace(videoSource=2)]
        pictureInPicture = []
    monitor.isInterruptionRequested = lambda: done['value']
    monitor._read_input_names = Mock(return_value={})
    waits = []
    monitor._wait_interruptible = lambda seconds: waits.append(seconds) or False
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: None)
    log = Mock()
    monkeypatch.setattr(module, 'logger', log)
    # Old implementation loops forever; bound it and still assert reconnection.
    reads = {'n': 0}
    old_interrupted = monitor.isInterruptionRequested
    def interrupted():
        reads['n'] += 1
        return old_interrupted() or reads['n'] > 30
    monitor.isInterruptionRequested = interrupted
    monitor._run_with_retry(SimpleNamespace(ATEMMax=Client))
    assert len(clients) == 2
    assert waits == [ATEM_RETRY_POLICY.backoffs[0]]
    assert monitor.state == ATEMState.CONNECTED
    assert all(client.disconnect.call_count == 1 for client in clients)
    assert log.exception.call_count == 0
    assert log.warning.call_count == 1


def test_persistently_dead_sessions_exhaust_budget_and_close(monkeypatch):
    import adapters.atem_monitor as module
    monitor = ATEMMonitor('192.0.2.50')
    clients = []
    class Client:
        def __init__(self):
            self.disconnect = Mock()
            clients.append(self)
        def connect(self, ip): pass
        def waitForConnection(self, timeout): return True
        @property
        def programInput(self):
            raise ConnectionError('dead')
        pictureInPicture = []
    monitor._read_input_names = Mock(return_value={})
    monitor.isInterruptionRequested = lambda: False
    waits = []
    monitor._wait_interruptible = lambda seconds: waits.append(seconds) or False
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: None)
    monitor._run_with_retry(SimpleNamespace(ATEMMax=Client))
    assert len(clients) == ATEM_RETRY_POLICY.max_attempts
    assert waits == list(ATEM_RETRY_POLICY.backoffs)
    assert monitor.state == ATEMState.DISCONNECTED
    assert all(client.disconnect.call_count == 1 for client in clients)
