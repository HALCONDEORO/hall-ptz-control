"""A dead ATEM session must end the monitor thread so the supervisor can restart it.

_run_with_retry() connects with bounded retries and the supervisor restarts a
stopped monitor in ERROR state (is_atem_supervisor_healthy). But _poll_loop
used to swallow every exception and spin at 10 Hz forever: the thread never
ended, the supervisor saw a live thread and stayed idle, and the ATEM was
stuck in ERROR until the whole app restarted. The loop now drops the session
after a bounded run of consecutive failures so the existing restart path can
fire; transient hiccups below the threshold keep the session as before.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

# QApplication, never a bare QCoreApplication: see tests/test_atem_reconnect.py.
if not QApplication.instance():
    _app = QApplication(sys.argv)

import adapters.atem_monitor as atem_monitor
from adapters.atem_monitor import ATEMMonitor
from domain.atem_state import ATEMState

# The contract: about three seconds of solid poll failure (30 cycles at the
# 0.1 s cadence) means the session is dead; fewer than that is a transient
# hiccup — a micro-outage must never cost the session.
MAX_FAILURES = getattr(atem_monitor, "_MAX_CONSECUTIVE_POLL_FAILURES", 30)


def _always_failing_input(calls):
    class _ProgramInput:
        def __getitem__(self, index):
            calls.append(1)
            raise OSError("session lost")
    return _ProgramInput()


def test_poll_loop_drops_session_after_bounded_consecutive_failures():
    """The loop returns after ~1s of solid failure instead of spinning forever."""
    monitor = ATEMMonitor("192.0.2.30")
    calls = []
    atem = MagicMock()
    atem.programInput = _always_failing_input(calls)
    states = []
    monitor.state_changed.connect(states.append, Qt.DirectConnection)
    monitor._emit_state(ATEMState.CONNECTED)

    # The loop would spin for all 90 iterations on the unfixed code.
    with patch.object(monitor, "isInterruptionRequested",
                      side_effect=[False] * (3 * MAX_FAILURES) + [True]), \
            patch('adapters.atem_monitor.time.sleep'):
        monitor._poll_loop(atem)

    assert len(calls) == MAX_FAILURES
    assert states == [ATEMState.CONNECTED, ATEMState.ERROR]


def test_transient_failures_below_threshold_keep_the_session():
    """Fewer consecutive failures than the threshold must not drop the session."""
    monitor = ATEMMonitor("192.0.2.30")

    class _FlakyInput:
        def __init__(self):
            self.calls = 0

        def __getitem__(self, index):
            self.calls += 1
            if self.calls <= MAX_FAILURES - 1:
                raise OSError("transient")
            if self.calls == MAX_FAILURES + 1:
                monitor.requestInterruption()
            item = MagicMock()
            item.videoSource = 3
            return item

    flaky = _FlakyInput()
    atem = MagicMock()
    atem.programInput = flaky
    states = []
    monitor.state_changed.connect(states.append, Qt.DirectConnection)
    monitor._emit_state(ATEMState.CONNECTED)

    with patch.object(monitor, "isInterruptionRequested",
                      side_effect=[False] * (MAX_FAILURES + 1) + [True]), \
            patch('adapters.atem_monitor.time.sleep'):
        monitor._poll_loop(atem)

    assert flaky.calls == MAX_FAILURES + 1  # loop survived the flaky streak
    assert states == [ATEMState.CONNECTED, ATEMState.ERROR, ATEMState.CONNECTED]


def test_run_with_retry_thread_ends_in_error_after_session_drop():
    """After the drop, the monitor thread ends in ERROR (supervisor-restartable)."""
    monitor = ATEMMonitor("192.0.2.30")
    calls = []
    client = MagicMock()
    client.waitForConnection.return_value = True
    client.programInput = _always_failing_input(calls)
    pyatemmax = MagicMock()
    pyatemmax.ATEMMax.return_value = client
    states = []
    monitor.state_changed.connect(states.append, Qt.DirectConnection)

    with patch.object(monitor, "isInterruptionRequested",
                      side_effect=[False] * (3 * MAX_FAILURES) + [True]), \
            patch('adapters.atem_monitor.time.sleep'):
        monitor._run_with_retry(pyatemmax)

    assert len(calls) == MAX_FAILURES          # dropped, not spun until interrupt
    assert states[-1] == ATEMState.ERROR       # terminal state for the supervisor
    # The dead client must be closed so the next monitor gets a clean session.
    closed = any(getattr(client, m).called for m in ("disconnect", "close", "stop"))
    assert closed
