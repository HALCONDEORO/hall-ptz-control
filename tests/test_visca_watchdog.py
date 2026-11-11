"""Tests for ui/visca_watchdog — the Qt/state shell of the speed watchdog.

The pure decision rules are locked by tests/test_adaptive_speed.py. These
tests pin the shell that applies them to the window: the per-channel state is
advanced, caps are written to both the window and the camera port, recovery is
scheduled (or blocked) through QTimer.singleShot, and unknown command types
are ignored. Behaviour matches the pre-extraction MainWindow methods.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from domain.adaptive_speed import fresh_channel_state
from ui import visca_watchdog as vw


def _window():
    return SimpleNamespace(
        _watchdog_state={'move': fresh_channel_state(), 'zoom_drive': fresh_channel_state()},
        _pan_cap=24,
        _tilt_cap=20,
        _zoom_drive_cap=7,
        _camera_port=SimpleNamespace(pan_cap=24, tilt_cap=20, zoom_drive_cap=7),
        _WATCHDOG_COOLDOWN=1.5,
        _WATCHDOG_RECOVERY_MS=20_000,
        _WATCHDOG_WINDOW_SECS=300.0,
        _WATCHDOG_MAX_RETRIES=3,
    )


class TestOnViscaSpeedError:

    def test_unknown_command_type_is_ignored(self):
        w = _window()
        with patch.object(vw.QTimer, 'singleShot') as timer:
            vw.on_visca_speed_error(w, '192.0.2.1', 'home')
        timer.assert_not_called()
        assert (w._pan_cap, w._tilt_cap) == (24, 20)
        assert (w._camera_port.pan_cap, w._camera_port.tilt_cap) == (24, 20)

    def test_first_error_reduces_move_caps_and_schedules_recovery(self):
        w = _window()
        with patch.object(vw.time, 'monotonic', return_value=100.0), \
                patch.object(vw.QTimer, 'singleShot') as timer:
            vw.on_visca_speed_error(w, '192.0.2.1', 'move')
        assert w._pan_cap < 24 and w._tilt_cap < 20
        assert w._camera_port.pan_cap == w._pan_cap
        assert w._camera_port.tilt_cap == w._tilt_cap
        timer.assert_called_once()
        assert timer.call_args[0][0] == 20_000
        assert w._watchdog_state['move']['retries'] == 1

    def test_error_within_cooldown_is_ignored(self):
        w = _window()
        with patch.object(vw.QTimer, 'singleShot'):
            with patch.object(vw.time, 'monotonic', return_value=100.0):
                vw.on_visca_speed_error(w, '192.0.2.1', 'move')
            caps_after_first = (w._pan_cap, w._tilt_cap)
            with patch.object(vw.time, 'monotonic', return_value=101.0):
                vw.on_visca_speed_error(w, '192.0.2.1', 'move')
        assert (w._pan_cap, w._tilt_cap) == caps_after_first
        assert w._watchdog_state['move']['retries'] == 1

    def test_last_retry_reduces_without_scheduling_recovery(self):
        w = _window()
        w._watchdog_state['move'] = {
            'last_reduction': 100.0, 'window_start': 100.0, 'retries': 2,
        }
        with patch.object(vw.time, 'monotonic', return_value=200.0), \
                patch.object(vw.QTimer, 'singleShot') as timer:
            vw.on_visca_speed_error(w, '192.0.2.1', 'move')
        assert w._pan_cap < 24          # reduction still applied
        timer.assert_not_called()       # but no further recovery attempt
        assert w._watchdog_state['move']['retries'] == 3

    def test_budget_spent_applies_nothing(self):
        w = _window()
        w._watchdog_state['move'] = {
            'last_reduction': 100.0, 'window_start': 100.0, 'retries': 3,
        }
        with patch.object(vw.time, 'monotonic', return_value=200.0), \
                patch.object(vw.QTimer, 'singleShot') as timer:
            vw.on_visca_speed_error(w, '192.0.2.1', 'move')
        assert (w._pan_cap, w._tilt_cap) == (24, 20)
        timer.assert_not_called()

    def test_zoom_drive_channel_reduces_its_own_cap(self):
        w = _window()
        with patch.object(vw.time, 'monotonic', return_value=100.0), \
                patch.object(vw.QTimer, 'singleShot'):
            vw.on_visca_speed_error(w, '192.0.2.1', 'zoom_drive')
        assert w._zoom_drive_cap < 7
        assert w._camera_port.zoom_drive_cap == w._zoom_drive_cap
        assert (w._pan_cap, w._tilt_cap) == (24, 20)  # move channel untouched


class TestRecoverCap:

    def test_recovers_one_step_and_updates_port(self):
        w = _window()
        w._pan_cap, w._tilt_cap = 20, 16
        w._camera_port.pan_cap, w._camera_port.tilt_cap = 20, 16
        w._watchdog_state['move']['retries'] = 1
        vw.recover_cap(w, 'move')
        assert w._pan_cap > 20 and w._tilt_cap > 16
        assert w._camera_port.pan_cap == w._pan_cap
        assert w._camera_port.tilt_cap == w._tilt_cap

    def test_noop_when_retry_budget_is_spent(self):
        w = _window()
        w._watchdog_state['move']['retries'] = 3
        w._pan_cap = 20
        vw.recover_cap(w, 'move')
        assert w._pan_cap == 20
        assert w._camera_port.pan_cap == 24

    def test_noop_for_unknown_channel(self):
        w = _window()
        vw.recover_cap(w, 'home')
        assert (w._pan_cap, w._tilt_cap, w._zoom_drive_cap) == (24, 20, 7)
