"""Tests for ui/shutdown_intent_dialog — the operator's shutdown choice.

Pins the behaviour extracted from MainWindow._ask_shutdown_intent:
- during login/splash (no normal work) the dialog is skipped entirely and
  the app keeps cameras on;
- the dialog offers keep / power-off / cancel, with cancel as BOTH the
  default and the escape button (a stray Enter or tap never powers off);
- the power-off button carries the destructive style;
- the clicked button maps to the right ShutdownIntent.

QMessageBox is faked at the module boundary — no real dialog, offscreen-safe.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication

if not QApplication.instance():
    _app = QApplication(sys.argv)

from domain.shutdown_intent import ShutdownIntent
from ui import shutdown_intent_dialog as sid


class _FakeButton:
    def __init__(self):
        self.stylesheet = ""

    def setStyleSheet(self, qss):
        self.stylesheet = qss


class _FakeMessageBox:
    """Records the dialog configuration and answers with a chosen button."""

    YesRole = 0
    NoRole = 1
    RejectRole = 2
    next_click = "cancel"  # class-level dial: which button exec_() "clicks"

    def __init__(self, _parent):
        self.buttons = {}
        self.default_button = None
        self.escape_button = None

    def setWindowTitle(self, _t):
        pass

    def setText(self, _t):
        pass

    def addButton(self, text, role):
        btn = _FakeButton()
        self.buttons[text] = btn
        return btn

    def setDefaultButton(self, btn):
        self.default_button = btn

    def setEscapeButton(self, btn):
        self.escape_button = btn

    def exec_(self):
        self.clicked = self.buttons[{
            "keep": "Keep cameras on",
            "off": "Power off cameras",
        }.get(self.next_click, "Cancel")]

    def clickedButton(self):
        return self.clicked


def _window(normal_work_active=True):
    return SimpleNamespace(_normal_work_active=normal_work_active)


def _run(click, normal_work_active=True):
    _FakeMessageBox.next_click = click
    seen = {}

    def capture(parent):
        box = _FakeMessageBox(parent)
        seen["box"] = box
        return box

    with patch.object(sid, "QMessageBox", side_effect=capture), \
            patch.object(sid, "fit_message_box_buttons", lambda _b: None), \
            patch.object(sid, "destructive_message_button_qss", return_value="RED"):
        return sid.ask_shutdown_intent(_window(normal_work_active)), seen.get("box")


class TestLoginSplashGuard:
    def test_no_dialog_before_work_starts(self):
        intent, box = _run("off", normal_work_active=False)
        assert intent is ShutdownIntent.EXIT_KEEP_CAMERAS_ON
        assert box is None  # dialog never constructed


class TestDialogWiring:
    def test_safe_defaults_are_cancel(self):
        intent, box = _run("cancel")
        assert intent is ShutdownIntent.CANCEL
        assert box.default_button is box.buttons["Cancel"]
        assert box.escape_button is box.buttons["Cancel"]

    def test_power_off_button_is_destructive_styled(self):
        _, box = _run("cancel")
        assert box.buttons["Power off cameras"].stylesheet == "RED"
        assert box.buttons["Keep cameras on"].stylesheet == ""


class TestIntentMapping:
    def test_keep_cameras_on(self):
        intent, _ = _run("keep")
        assert intent is ShutdownIntent.EXIT_KEEP_CAMERAS_ON

    def test_power_off_cameras(self):
        intent, _ = _run("off")
        assert intent is ShutdownIntent.EXIT_AND_POWER_OFF_CAMERAS

    def test_cancel(self):
        intent, _ = _run("cancel")
        assert intent is ShutdownIntent.CANCEL
