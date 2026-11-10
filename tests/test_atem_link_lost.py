"""A dropped ATEM link must not leave the monitor CONNECTED on a stale program.

PyATEMMax keeps the last programInput after the link drops and only sets
``connected = False`` while it retries on its own.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

if not QApplication.instance():
    _app = QApplication(sys.argv)

from adapters.atem_monitor import ATEMMonitor
from domain.atem_state import ATEMState


class _Inputs:
    def __getitem__(self, index):
        return SimpleNamespace(videoSource=3)  # stale value, never raises


def _run(connected_seq):
    it = iter(connected_seq)

    class _A(SimpleNamespace):
        @property
        def connected(self):
            return next(it)

    atem = _A(programInput=_Inputs())
    monitor = ATEMMonitor("192.0.2.1")
    states, verified = [], []
    monitor.state_changed.connect(states.append, Qt.DirectConnection)
    monitor.program_verified.connect(verified.append, Qt.DirectConnection)
    monitor._emit_state(ATEMState.CONNECTED)
    n = len(connected_seq)
    with patch.object(monitor, "isInterruptionRequested",
                      side_effect=[False] * n + [True]), \
         patch("adapters.atem_monitor.time.sleep"), \
         patch.object(monitor, "_poll_pip"):
        monitor._poll_loop(atem)
    return monitor, states, verified


def test_link_lost_marks_error_once_and_recovers_with_reverification():
    monitor, states, verified = _run([True, False, False, True])
    assert states == [ATEMState.CONNECTED, ATEMState.ERROR, ATEMState.CONNECTED]
    assert verified == [3, 3]  # re-verified after the link came back


def test_link_lost_does_not_claim_program_while_down():
    _m, states, verified = _run([False, False])
    assert states == [ATEMState.CONNECTED, ATEMState.ERROR]
    assert verified == []
