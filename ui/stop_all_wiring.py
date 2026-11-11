"""STOP ALL button wiring.

connect_stop_all(window) inserts a red STOP ALL button into the right
panel's outer layout (below the PTZ controls and the "Camera not found"
placeholder) and connects it to the operator STOP ALL action:

  1. Emit CAMERA_STOP for every logical camera on the bus emergency lane.
     This retires each camera's MotionAdmission ticket, so a move command
     still queued on the bus cannot execute after the stop
     (OPERATOR_GUIDE: STOP ALL "drains queued movement commands").
  2. Call RuntimeSafetyService.stop_all_cameras(), the product-level STOP
     authority (#779): it attempts every configured camera, bypasses
     session guards, and reports partial failure without raising.

A partial or total failure — including the safety service not being
wired — is shown in a small red label under the button: visible but
non-blocking, so the operator sees that a camera may still be moving
without a modal dialog stealing the joystick.  A single QTimer hides
the notice; a new failure restarts it, so the notice for the latest
failure always survives a full timeout.

Placement matters: the PTZ block (_motion_widget) is disabled when no
camera is connected, and the controls container is hidden in that state,
but STOP ALL must always be available — a runaway camera is exactly the
case where connection state is uncertain.  The button therefore lives in
the panel's outer layout, outside both subtrees, stays visible with or
without a session, and needs no confirmation dialog: it is non-
destructive (no standby, no state clear, no ATEM policy) and idempotent.
"""

from __future__ import annotations

import logging

from PyQt5 import QtCore
from PyQt5.QtWidgets import QLabel, QPushButton

from core.events import EventType

logger = logging.getLogger(__name__)

_BUTTON_STYLE = (
    "QPushButton {"
    "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
    "    stop:0 #D02020, stop:1 #901010);"
    "  border: none; border-radius: 10px;"
    "  font: 700 14px 'Inter Tight', 'Segoe UI'; color: white;"
    "}"
    "QPushButton:pressed { background: #600808; }"
)

_NOTICE_STYLE = (
    "QLabel { font: 600 12px 'Inter Tight', 'Segoe UI';"
    " color: #E05050; padding: 2px 4px; }"
)

_NOTICE_TIMEOUT_MS = 6000


def _show_notice(notice: QLabel, hide_timer: QtCore.QTimer, text: str) -> None:
    """Show the failure notice and restart the single hide timer."""
    notice.setText(text)
    notice.show()
    hide_timer.start()  # restart: an earlier failure never hides a later one


def _stop_all(window, notice: QLabel, hide_timer: QtCore.QTimer) -> None:
    """Run the operator STOP ALL action. Never raises into the Qt slot."""
    bus = getattr(window, "_bus", None)
    if bus is not None:
        # Logical cameras 1/2 match the CAMERA_STOP payload convention used
        # by JoystickAdapter and the controller's emergency lane.
        for cam in (1, 2):
            bus.emit(EventType.CAMERA_STOP, camera=cam)
    service = getattr(window, "_runtime_safety_svc", None)
    if service is None:
        logger.warning("STOP ALL pressed but RuntimeSafetyService is not wired")
        _show_notice(notice, hide_timer, "STOP ALL: safety service unavailable")
        return
    result = service.stop_all_cameras()
    if result.ok:
        notice.hide()
        hide_timer.stop()
        return
    logger.warning("STOP ALL partial failure: %s", result.message)
    _show_notice(notice, hide_timer, f"STOP ALL: {result.message}")


def connect_stop_all(window) -> QPushButton:
    """Insert the STOP ALL button into the right panel and wire it."""
    panel = window._right_panel
    layout = panel._container.layout()
    btn = QPushButton("STOP ALL", panel._container)
    btn.setFixedHeight(44)
    btn.setStyleSheet(_BUTTON_STYLE)
    notice = QLabel(panel._container)
    notice.setStyleSheet(_NOTICE_STYLE)
    notice.setWordWrap(True)
    notice.hide()
    hide_timer = QtCore.QTimer(panel._container)
    hide_timer.setSingleShot(True)
    hide_timer.setInterval(_NOTICE_TIMEOUT_MS)
    hide_timer.timeout.connect(notice.hide)
    btn.clicked.connect(lambda: _stop_all(window, notice, hide_timer))
    anchor = panel._no_camera_label
    layout.insertWidget(layout.indexOf(anchor) + 1, btn)
    layout.insertWidget(layout.indexOf(btn) + 1, notice)
    return btn
