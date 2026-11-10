"""Shutdown-intent dialog for MainWindow.

Extracted from ui/main_window.py to keep the file inside its anti-god-object
budget (tests/test_ui_god_object_budget.py). Behaviour is identical to the
former MainWindow._ask_shutdown_intent body; the window keeps a thin delegate
so tests can still patch ``window._ask_shutdown_intent``.
"""

from __future__ import annotations

from PyQt5.QtWidgets import QMessageBox

from domain.shutdown_intent import ShutdownIntent
from ui.message_box_layout import destructive_message_button_qss, fit_message_box_buttons


def ask_shutdown_intent(window) -> "ShutdownIntent":
    """Show a shutdown dialog and return the operator's explicit choice.

    Returns ShutdownIntent so the caller decides whether to send standby.

    If the app is still in login/splash (work not yet started), skips the
    camera-power-off option entirely and returns EXIT_KEEP_CAMERAS_ON
    directly without showing a dialog.
    """
    if not window._normal_work_active:
        return ShutdownIntent.EXIT_KEEP_CAMERAS_ON
    msg = QMessageBox(window)
    msg.setWindowTitle("Close application")
    msg.setText("How do you want to close the application?")
    btn_keep = msg.addButton("Keep cameras on",  QMessageBox.YesRole)
    btn_off  = msg.addButton("Power off cameras", QMessageBox.NoRole)
    btn_cancel = msg.addButton("Cancel", QMessageBox.RejectRole)
    # Safe default/escape: a stray Enter or tap cancels, never powers off.
    msg.setDefaultButton(btn_cancel)
    msg.setEscapeButton(btn_cancel)
    btn_off.setStyleSheet(destructive_message_button_qss())
    fit_message_box_buttons(msg)
    msg.exec_()
    clicked = msg.clickedButton()
    if clicked is btn_keep:
        return ShutdownIntent.EXIT_KEEP_CAMERAS_ON
    if clicked is btn_off:
        return ShutdownIntent.EXIT_AND_POWER_OFF_CAMERAS
    return ShutdownIntent.CANCEL
