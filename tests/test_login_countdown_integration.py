#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""
test_login_countdown_integration.py — Real-Qt integration tests for the operator
auto-entry countdown.

Unlike test_login_screen_password_warning.py (which drives unbound methods with a
MagicMock self), these tests build a *real* LoginScreen on an offscreen
QApplication, so they exercise the actual widget wiring:

  • default boot mode is Operator (never a stale persisted Admin role)
  • Operator ALWAYS shows the countdown, with no password field and "Start now"
  • pressing "Start now" (or the countdown reaching 0) logs in as CAMERA_OPERATOR
  • switching to Admin cancels the countdown and reveals the password field

Run isolated (the full Qt suite segfaults under Py3.14 offscreen):
    QT_QPA_PLATFORM=offscreen python -m pytest tests/test_login_countdown_integration.py
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from conftest import ensure_real_qt, is_poisoned_by_qt_stub  # noqa: E402
from domain.call_set_policy import OperatingMode  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _real_qt():
    """Ensure the real PyQt5 is in sys.modules (drop any collection-time stub)."""
    ensure_real_qt()


@pytest.fixture
def qapp(_real_qt):
    # Function-scoped, not module-scoped: under pytest-forked each test runs in
    # its own forked child, so a QApplication built once and shared across
    # tests in this module would be inherited across fork() boundaries from
    # whichever test happened to build it first — Qt does not support that and
    # aborts the next child that touches it. conftest.py's autouse
    # _qapp_available fixture already guarantees one exists in *this* process.
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def login(qapp):
    from ui.login_screen import LoginScreen
    if is_poisoned_by_qt_stub(LoginScreen):
        pytest.skip("ui.login_screen was imported under a PyQt5 stub by another "
                    "test module — run this file in isolation")
    widget = LoginScreen()
    widget._set_mode("operator")
    yield widget
    widget.deleteLater()


class TestBootDefaultsToOperator:
    def test_init_login_mode_starts_in_operator(self, login):
        login._init_login_mode()
        assert login._mode == "operator"


class TestOperatorAlwaysShowsCountdown:
    """Operator entry needs no password: the countdown is always shown."""

    def test_operator_auto_is_true(self, login):
        assert login._operator_auto is True

    def test_password_field_hidden(self, login):
        assert login.password_input.isHidden()

    def test_countdown_timer_running(self, login):
        assert login._countdown_timer is not None
        assert login._countdown_timer.isActive()

    def test_button_shows_start_now_with_seconds(self, login):
        assert "Start now" in login.login_btn.text()
        assert "s" in login.login_btn.text()  # "Start now  ·  10s"

    def test_start_now_logs_in_as_operator(self, login):
        received: list[bool] = []
        login.login_successful.connect(lambda: received.append(True))
        login._on_primary_action()  # press "Start now"
        assert received == [True]
        assert login.authenticated is True
        assert login.authenticated_role == OperatingMode.CAMERA_OPERATOR

    def test_countdown_tick_reaches_login(self, login):
        received: list[bool] = []
        login.login_successful.connect(lambda: received.append(True))
        login._countdown_remaining = 1
        login._tick_countdown()  # 1 → 0 → auto-enter
        assert received == [True]
        assert login.authenticated_role == OperatingMode.CAMERA_OPERATOR

    def test_countdown_decrements_button(self, login):
        login._countdown_remaining = 8
        login._tick_countdown()  # 8 → 7, still above zero
        assert login._countdown_remaining == 7
        assert "7s" in login.login_btn.text()


class TestSwitchToAdminCancelsCountdown:
    def test_switch_to_admin_stops_countdown_and_shows_password(self, login):
        assert login._countdown_timer.isActive()
        login._set_mode("admin")
        assert login._mode == "admin"
        assert login._operator_auto is False
        assert not login._countdown_timer.isActive()
        assert not login.password_input.isHidden()

    def test_switch_back_to_operator_restarts_countdown(self, login):
        login._set_mode("admin")
        login._set_mode("operator")
        assert login._operator_auto is True
        assert login._countdown_timer.isActive()
        assert login.password_input.isHidden()


class TestModeSwitchKeepsLockoutCounter:
    """Regression: toggling Operator <-> Admin must not reset the failed-attempt
    counter. _set_mode used to zero it, so two clicks wiped the progressive
    lockout and password guessing continued at full speed."""

    def test_mode_toggle_preserves_attempts(self, login):
        login._set_mode("admin")
        login.attempts = 3
        login._on_switch_user()   # admin -> operator
        login._on_switch_user()   # operator -> admin
        assert login._mode == "admin"
        assert login.attempts == 3

    def test_lockout_duration_uses_accumulated_attempts(self, login):
        login._set_mode("admin")
        login.attempts = 3
        login._set_mode("operator")
        login._set_mode("admin")
        # Next failure must schedule attempt #4's lockout (30s), not restart
        # at the free first entries of the schedule.
        login._on_login_failure()
        assert login.attempts == 4
        assert login.is_locked is True
        login.lockout_timer.stop()


class TestLockoutSurvivesModeToggle:
    """Regression: a running password lockout must survive mode toggles.

    Before the fix, switching to Operator cleared is_locked and re-enabled the
    button; switching back to Admin left ACCESS enabled with the password
    field disabled, and attempts resumed before the lockout timer ended."""

    def _lock(self, login):
        login._set_mode("admin")
        login.attempts = 2
        login._on_login_failure()   # attempt 3 -> 10s lockout
        assert login.is_locked is True
        assert login.lockout_timer.isActive()

    def _finish_lockout(self, login):
        login.remaining_seconds = 1
        login.lockout_timer.timeout.emit()   # 1 -> 0 -> unlock path

    @staticmethod
    def _force_schedule_bypass(monkeypatch):
        import application.schedule_config as sc
        monkeypatch.setattr(sc, "is_within_schedule", lambda: True)

    def test_toggle_to_operator_keeps_lock(self, login, monkeypatch):
        self._force_schedule_bypass(monkeypatch)
        self._lock(login)
        login._on_switch_user()   # -> operator auto-entry (bypass)
        assert login._mode == "operator"
        assert login._operator_auto is True
        assert login.is_locked is True
        assert not login.login_btn.isEnabled()
        assert not login._countdown_timer.isActive()

    def test_toggle_back_to_admin_keeps_form_disabled(self, login):
        self._lock(login)
        login._on_switch_user()   # -> operator
        login._on_switch_user()   # -> admin
        assert login._mode == "admin"
        assert login.is_locked is True
        assert not login.login_btn.isEnabled()
        assert not login.password_input.isEnabled()

    def test_unlock_in_operator_resumes_countdown(self, login, monkeypatch):
        self._force_schedule_bypass(monkeypatch)
        self._lock(login)
        login._on_switch_user()   # -> operator, countdown paused by the lock
        self._finish_lockout(login)
        assert login.is_locked is False
        assert login.login_btn.isEnabled()
        assert login._countdown_timer.isActive()

    def test_unlock_in_admin_reenables_password_field(self, login):
        self._lock(login)
        self._finish_lockout(login)
        assert login.is_locked is False
        assert login.password_input.isEnabled()
        assert login.login_btn.isEnabled()

    def test_unlock_in_operator_then_admin_reenables_password_field(self, login, monkeypatch):
        # Regression: when the lockout timer ends while Operator auto-entry is
        # active, the unlock path used to leave password_input disabled; the
        # next switch to Admin only disables the field while is_locked, so the
        # form stayed unusable until an app restart.
        self._force_schedule_bypass(monkeypatch)
        self._lock(login)
        login._on_switch_user()        # -> operator (auto-entry, lock pauses it)
        assert login._operator_auto is True
        self._finish_lockout(login)    # lockout ends in Operator mode
        assert login.is_locked is False
        assert login.password_input.isEnabled()
        login._on_switch_user()        # -> admin
        assert login._mode == "admin"
        assert login.password_input.isEnabled()
        assert login.login_btn.isEnabled()
