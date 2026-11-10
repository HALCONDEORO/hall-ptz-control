#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""
test_role_elevation_overlay.py — Unit tests for RoleElevationOverlay._try_login
and ._cancel.

Methods are exercised as unbound functions with a MagicMock stub.
Qt stubs are injected before import; no QApplication is needed.
"""
from __future__ import annotations

import sys
import types

import pytest
from unittest.mock import MagicMock, patch



# ── Qt stubs ──────────────────────────────────────────────────────────────────

def _ensure_stubs() -> None:
    for mod in ("PyQt5", "PyQt5.QtCore", "PyQt5.QtWidgets", "PyQt5.QtGui"):
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)

    qtc = sys.modules["PyQt5.QtCore"]
    for a in ("Qt",):
        if not hasattr(qtc, a):
            setattr(qtc, a, MagicMock())

    qtw = sys.modules["PyQt5.QtWidgets"]
    for a in ("QWidget", "QFrame", "QGraphicsDropShadowEffect", "QHBoxLayout",
              "QLabel", "QLineEdit", "QPushButton", "QVBoxLayout"):
        if not hasattr(qtw, a):
            setattr(qtw, a, MagicMock)

    qtg = sys.modules["PyQt5.QtGui"]
    for a in ("QColor", "QFont", "QPainter"):
        if not hasattr(qtg, a):
            setattr(qtg, a, MagicMock)
    if not hasattr(qtg, "QFont"):
        class _FF:
            Bold = 75
            Normal = 50
            def __init__(self, *a, **k): pass
        qtg.QFont = _FF  # type: ignore[attr-defined]
    else:
        if not hasattr(qtg.QFont, "Bold"):
            qtg.QFont.Bold = 75


_ensure_stubs()

import ui.role_elevation_overlay as _reo  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stub(pwd_text: str = "") -> MagicMock:
    stub = MagicMock()
    stub._pwd_input.text.return_value = pwd_text
    stub._on_success = MagicMock()
    stub._on_cancel  = MagicMock()
    return stub


@pytest.fixture(autouse=True)
def _reset_shared_lockout():
    """El estado de bloqueo es compartido (módulo): aislarlo entre tests."""
    _reo._SHARED_LOCKOUT.attempts = 0
    _reo._SHARED_LOCKOUT.lock_until = 0.0
    yield
    _reo._SHARED_LOCKOUT.attempts = 0
    _reo._SHARED_LOCKOUT.lock_until = 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  _try_login()
# ══════════════════════════════════════════════════════════════════════════════

class TestTryLogin:
    """_try_login() consults application.authentication.verify_admin and calls
    on_success or shows an error. Elevation requires the ADMIN password (with the
    documented migration fallback inside verify_admin)."""

    def test_empty_password_shows_error(self):
        stub = _stub(pwd_text="")
        _reo.RoleElevationOverlay._try_login(stub)
        stub._lbl_err.setText.assert_called_once()
        msg = stub._lbl_err.setText.call_args[0][0]
        assert "password" in msg.lower() or "enter" in msg.lower()

    def test_empty_password_does_not_call_on_success(self):
        stub = _stub(pwd_text="")
        _reo.RoleElevationOverlay._try_login(stub)
        stub._on_success.assert_not_called()

    def test_wrong_password_shows_error(self):
        stub = _stub(pwd_text="wrong")
        with patch("application.authentication.verify_admin", return_value=False):
            _reo.RoleElevationOverlay._try_login(stub)
        stub._lbl_err.setText.assert_called_once()
        stub._on_success.assert_not_called()

    def test_wrong_password_increments_attempts(self):
        stub = _stub(pwd_text="wrong")
        with patch("application.authentication.verify_admin", return_value=False):
            _reo.RoleElevationOverlay._try_login(stub)
        assert _reo._SHARED_LOCKOUT.attempts == 1

    def test_wrong_password_clears_input(self):
        stub = _stub(pwd_text="wrong")
        with patch("application.authentication.verify_admin", return_value=False):
            _reo.RoleElevationOverlay._try_login(stub)
        stub._pwd_input.clear.assert_called_once()

    def test_correct_password_calls_on_success(self):
        stub = _stub(pwd_text="secret")
        with patch("application.authentication.verify_admin", return_value=True):
            _reo.RoleElevationOverlay._try_login(stub)
        stub._on_success.assert_called_once()

    def test_correct_password_hides_overlay(self):
        stub = _stub(pwd_text="secret")
        with patch("application.authentication.verify_admin", return_value=True):
            _reo.RoleElevationOverlay._try_login(stub)
        stub.hide.assert_called_once()

    def test_correct_password_does_not_show_error(self):
        stub = _stub(pwd_text="secret")
        with patch("application.authentication.verify_admin", return_value=True):
            _reo.RoleElevationOverlay._try_login(stub)
        stub._lbl_err.setText.assert_not_called()

    def test_rejected_password_does_not_elevate(self):
        # verify_admin returns False when no password matches (incl. nothing
        # configured) — the overlay treats it as a wrong password and stays put.
        stub = _stub(pwd_text="anything")
        with patch("application.authentication.verify_admin", return_value=False):
            _reo.RoleElevationOverlay._try_login(stub)
        stub._lbl_err.setText.assert_called_once()
        stub._on_success.assert_not_called()

    def test_attempts_counter_accumulates(self):
        stub = _stub(pwd_text="wrong")
        _reo._SHARED_LOCKOUT.attempts = 2
        with patch("application.authentication.verify_admin", return_value=False):
            _reo.RoleElevationOverlay._try_login(stub)
        assert _reo._SHARED_LOCKOUT.attempts == 3

    def test_error_message_includes_attempt_count(self):
        stub = _stub(pwd_text="wrong")
        with patch("application.authentication.verify_admin", return_value=False):
            _reo.RoleElevationOverlay._try_login(stub)
        msg = stub._lbl_err.setText.call_args[0][0]
        assert "1" in msg  # attempt number shown


# ══════════════════════════════════════════════════════════════════════════════
#  _cancel()
# ══════════════════════════════════════════════════════════════════════════════

class TestCancel:
    """_cancel() hides the overlay and fires on_cancel."""

    def test_calls_on_cancel(self):
        stub = _stub()
        _reo.RoleElevationOverlay._cancel(stub)
        stub._on_cancel.assert_called_once()

    def test_hides_overlay(self):
        stub = _stub()
        _reo.RoleElevationOverlay._cancel(stub)
        stub.hide.assert_called_once()

    def test_does_not_call_on_success(self):
        stub = _stub()
        _reo.RoleElevationOverlay._cancel(stub)
        stub._on_success.assert_not_called()



# ══════════════════════════════════════════════════════════════════════════════
#  Bloqueo progresivo (misma política que LoginScreen, #237)
# ══════════════════════════════════════════════════════════════════════════════

class TestProgressiveLockout:
    """El overlay de elevación es una segunda puerta al rol Admin: debe aplicar
    el mismo bloqueo progresivo que la pantalla de login. Sin él, dentro del
    horario de bypass del operador cualquiera puede fuerza-bruta la clave de
    administrador con intentos ilimitados."""

    def test_third_wrong_password_locks_out(self):
        import time as _t
        stub = _stub(pwd_text="wrong")
        _reo._SHARED_LOCKOUT.attempts = 2
        before = _t.monotonic()
        with patch("application.authentication.verify_admin", return_value=False), \
             patch.object(_reo.RoleElevationOverlay, "_start_lockout_timer"):
            _reo.RoleElevationOverlay._try_login(stub)
        assert _reo._SHARED_LOCKOUT.lock_until > before + 5  # schedule[2] == 10s
        stub._pwd_input.setEnabled.assert_called_with(False)
        msg = stub._lbl_err.setText.call_args[0][0]
        assert "Locked" in msg

    def test_locked_overlay_rejects_attempt_without_verifying(self):
        import time as _t
        stub = _stub(pwd_text="guess")
        _reo._SHARED_LOCKOUT.lock_until = _t.monotonic() + 100
        with patch("application.authentication.verify_admin") as verify:
            _reo.RoleElevationOverlay._try_login(stub)
        verify.assert_not_called()
        stub._on_success.assert_not_called()
        msg = stub._lbl_err.setText.call_args[0][0]
        assert "Locked" in msg

    def test_show_overlay_does_not_reset_attempt_counter(self):
        # Reabrir el overlay (Cancel + Admin Mode) NO debe borrar el contador:
        # era el mismo vector de borrado que #237 corrigió en el toggle de modo.
        stub = _stub()
        _reo._SHARED_LOCKOUT.attempts = 5
        _reo.RoleElevationOverlay.show_overlay(stub)
        assert _reo._SHARED_LOCKOUT.attempts == 5

    def test_successful_elevation_resets_attempt_counter(self):
        stub = _stub(pwd_text="secret")
        _reo._SHARED_LOCKOUT.attempts = 5
        with patch("application.authentication.verify_admin", return_value=True):
            _reo.RoleElevationOverlay._try_login(stub)
        assert _reo._SHARED_LOCKOUT.attempts == 0
        stub._on_success.assert_called_once()

    def test_locking_one_instance_locks_the_other(self):
        """MainWindow crea DOS overlays (hotspot oculto y botón del panel):
        bloquear uno debe bloquear el otro, o alternarlos duplicaría intentos."""
        first, second = _stub(pwd_text="wrong"), _stub(pwd_text="guess")
        _reo._SHARED_LOCKOUT.attempts = 2
        with patch("application.authentication.verify_admin", return_value=False), \
             patch.object(_reo.RoleElevationOverlay, "_start_lockout_timer"):
            _reo.RoleElevationOverlay._try_login(first)  # 3er fallo → bloqueo
        with patch("application.authentication.verify_admin") as verify:
            _reo.RoleElevationOverlay._try_login(second)
        verify.assert_not_called()
        second._on_success.assert_not_called()
        msg = second._lbl_err.setText.call_args[0][0]
        assert "Locked" in msg

    def test_failure_message_has_no_hard_cap_wording(self):
        """Sin "X left": el bloqueo es progresivo, no un máximo de intentos."""
        stub = _stub(pwd_text="wrong")
        with patch("application.authentication.verify_admin", return_value=False):
            _reo.RoleElevationOverlay._try_login(stub)
        msg = stub._lbl_err.setText.call_args[0][0]
        assert "left" not in msg
