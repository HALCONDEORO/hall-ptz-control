"""Endpoint motion epochs. Locks cover queue admission, never confirmation waits."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import threading


@dataclass(frozen=True)
class MotionTicket:
    endpoint: str
    generation: int
    ready: threading.Event
    cancelled: threading.Event = field(default_factory=threading.Event)


class MotionAdmission:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.lock = threading.RLock()
        self._epochs = {}
        self._local = threading.local()

    def capture(self, camera_id):
        endpoint = self.endpoint(camera_id)
        with self.lock:
            if endpoint not in self._epochs:
                ready = threading.Event()
                ready.set()
                self._epochs[endpoint] = MotionTicket(endpoint, 0, ready)
            return self._epochs[endpoint]

    def retire(self, camera_id):
        with self.lock:
            previous = self.capture(camera_id)
            ticket = MotionTicket(previous.endpoint, previous.generation + 1,
                                  threading.Event())
            self._epochs[ticket.endpoint] = ticket
            previous.ready.set()  # Superseded waiters wake and fail their epoch check.
            return ticket

    def current(self, ticket):
        return self._epochs.get(ticket.endpoint) is ticket and not ticket.cancelled.is_set()

    def cancel(self, ticket):
        """Release waiters without authorizing a STOP that was never admitted."""
        with self.lock:
            ticket.cancelled.set()
            ticket.ready.set()

    @contextmanager
    def intent(self, ticket):
        previous = getattr(self._local, 'ticket', None)
        self._local.ticket = ticket
        try:
            yield
        finally:
            self._local.ticket = previous

    def ticket(self):
        return getattr(self._local, 'ticket', None)

    def admit(self, endpoint, send):
        ticket = self.ticket()
        if ticket is not None:
            ticket.ready.wait()
        with self.lock:
            if ticket is not None and (
                ticket.endpoint != endpoint or not self.current(ticket)
            ):
                return False
            return send()

    def commit(self, ticket, update):
        with self.lock:
            if self.current(ticket):
                update()
                return True
            return False

    def stop(self, ticket, send):
        try:
            with self.lock:
                if self.current(ticket):
                    return send()
                return False
        finally:
            ticket.ready.set()
