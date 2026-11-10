"""Bounded scripted VISCA peer. Binds ONLY IPv4 loopback on an ephemeral port.

Each Step consumes one FF-terminated command across sequential connections.
No implicit ACK or Completion is invented. Empty replies keep the socket open
and silent. All reply delays are relative to the preceding reply/command.
"""
from dataclasses import dataclass
import socket
import threading


@dataclass(frozen=True)
class Reply:
    data: bytes
    delay: float = 0.0


@dataclass(frozen=True)
class Step:
    expected: bytes | None = None
    replies: tuple[Reply, ...] = ()
    close: bool = False


class ScriptedViscaCamera:
    host = '127.0.0.1'

    def __init__(self, steps):
        self.steps = tuple(steps)
        if any(reply.delay < 0 for step in self.steps for reply in step.replies):
            raise ValueError('Reply delays must be nonnegative')
        self.received = []
        self.errors = []
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._listener = None
        self.thread = None

    def __enter__(self):
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind((self.host, 0))
        self.port = self._listener.getsockname()[1]
        self._listener.listen(2)
        self._listener.settimeout(0.05)
        self.thread = threading.Thread(target=self._run, daemon=True,
                                       name='VISCA-test-loopback')
        self.thread.start()
        return self

    def wait_received(self, count, timeout=2):
        with self._condition:
            return self._condition.wait_for(lambda: len(self.received) >= count
                                            or self.errors, timeout) and len(self.received) >= count

    def __exit__(self, exc_type, exc, traceback):
        self._stop.set()
        self.thread.join(2)
        self._listener.close()
        if self.thread.is_alive():
            raise AssertionError('VISCA test peer failed to stop')
        if exc_type is None and self.errors:
            raise AssertionError('VISCA test peer failed: ' + repr(self.errors))

    def _run(self):
        step_index = 0
        try:
            while not self._stop.is_set():
                try:
                    connection, _ = self._listener.accept()
                except socket.timeout:
                    continue
                with connection:
                    connection.settimeout(0.05)
                    pending = b''
                    while not self._stop.is_set():
                        try:
                            chunk = connection.recv(256)
                        except socket.timeout:
                            continue
                        if not chunk:
                            break
                        pending += chunk
                        if len(pending) > 1024:
                            raise AssertionError('Test command exceeds bounded frame budget')
                        close = False
                        while b'\xff' in pending:
                            body, pending = pending.split(b'\xff', 1)
                            command = body + b'\xff'
                            with self._condition:
                                self.received.append(command)
                                self._condition.notify_all()
                            if step_index >= len(self.steps):
                                raise AssertionError('Unexpected extra command: ' + command.hex())
                            step = self.steps[step_index]
                            step_index += 1
                            if step.expected is not None and command != step.expected:
                                raise AssertionError('Unexpected command: ' + command.hex())
                            for reply in step.replies:
                                if self._stop.wait(reply.delay):
                                    return
                                try:
                                    connection.sendall(reply.data)
                                except OSError:
                                    # Timeout/STOP clients deliberately retire streams
                                    # before a late reply. That is an expected scenario.
                                    break
                            if step.close:
                                close = True
                                break
                        if close:
                            break
        except Exception as error:
            with self._condition:
                self.errors.append(error)
                self._condition.notify_all()
