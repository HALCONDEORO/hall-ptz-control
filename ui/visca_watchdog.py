"""Qt/state shell of the VISCA adaptive-speed watchdog.

Extracted from MainWindow (god-object ratchet, tests/test_ui_god_object_budget.py).
The pure decision rules live in domain/adaptive_speed (locked by
tests/test_adaptive_speed.py); these functions only apply them to the window's
mutable state: the per-command channel state, the speed caps and the camera
port, plus the recovery timer. Behaviour is unchanged — MainWindow delegates.
"""

from __future__ import annotations

import logging
import time

from PyQt5.QtCore import QTimer

from config import PAN_SPEED_MAX, TILT_SPEED_MAX, ZOOM_DRIVE_MAX
from domain.adaptive_speed import (
    evaluate_speed_error,
    recovered_move_caps,
    recovered_zoom_drive_cap,
    reduced_move_caps,
    reduced_zoom_drive_cap,
)

logger = logging.getLogger(__name__)


def on_visca_speed_error(window, ip: str, cmd_type: str) -> None:
    if cmd_type not in window._watchdog_state:
        return
    now  = time.monotonic()
    next_state, decision = evaluate_speed_error(
        window._watchdog_state[cmd_type],
        now,
        cooldown=window._WATCHDOG_COOLDOWN,
        window_secs=window._WATCHDOG_WINDOW_SECS,
        max_retries=window._WATCHDOG_MAX_RETRIES,
    )
    window._watchdog_state[cmd_type] = next_state

    if not decision.apply_reduction:
        return

    apply_reduction(window, cmd_type, ip)

    # Programar intento de recuperación si quedan reintentos
    if decision.schedule_recovery:
        QTimer.singleShot(
            window._WATCHDOG_RECOVERY_MS,
            lambda ct=cmd_type: recover_cap(window, ct),
        )
    else:
        logger.warning(
            "Watchdog VISCA [%s] %s: %d reducciones en %.0f s — cap bloqueado hasta reinicio de sesión",
            cmd_type, ip, window._WATCHDOG_MAX_RETRIES, window._WATCHDOG_WINDOW_SECS,
        )


def apply_reduction(window, cmd_type: str, ip: str) -> None:
    if cmd_type == 'move':
        new_pan, new_tilt = reduced_move_caps(window._pan_cap, window._tilt_cap)
        changed = False
        if new_pan != window._pan_cap:
            window._pan_cap = new_pan
            window._camera_port.pan_cap = new_pan
            changed = True
        if new_tilt != window._tilt_cap:
            window._tilt_cap = new_tilt
            window._camera_port.tilt_cap = new_tilt
            changed = True
        if changed:
            logger.warning(
                "Watchdog VISCA [move] %s — pan_cap→%d  tilt_cap→%d",
                ip, window._pan_cap, window._tilt_cap,
            )
    elif cmd_type == 'zoom_drive':
        new_zoom = reduced_zoom_drive_cap(window._zoom_drive_cap)
        if new_zoom != window._zoom_drive_cap:
            window._zoom_drive_cap = new_zoom
            window._camera_port.zoom_drive_cap = new_zoom
            logger.warning(
                "Watchdog VISCA [zoom_drive] %s — zoom_drive_cap→%d",
                ip, window._zoom_drive_cap,
            )


def recover_cap(window, cmd_type: str) -> None:
    """Sube el cap un paso para comprobar si la cámara admite mayor velocidad."""
    st = window._watchdog_state.get(cmd_type)
    if st is None or st['retries'] >= window._WATCHDOG_MAX_RETRIES:
        return
    if cmd_type == 'move':
        window._pan_cap, window._tilt_cap = recovered_move_caps(
            window._pan_cap, window._tilt_cap,
            pan_max=PAN_SPEED_MAX, tilt_max=TILT_SPEED_MAX,
        )
        window._camera_port.pan_cap  = window._pan_cap
        window._camera_port.tilt_cap = window._tilt_cap
        logger.info(
            "Watchdog VISCA [move]: intento recuperación %d/%d — pan_cap→%d tilt_cap→%d",
            st['retries'], window._WATCHDOG_MAX_RETRIES, window._pan_cap, window._tilt_cap,
        )
    elif cmd_type == 'zoom_drive':
        window._zoom_drive_cap = recovered_zoom_drive_cap(
            window._zoom_drive_cap, zoom_max=ZOOM_DRIVE_MAX,
        )
        window._camera_port.zoom_drive_cap = window._zoom_drive_cap
        logger.info(
            "Watchdog VISCA [zoom_drive]: intento recuperación %d/%d — cap→%d",
            st['retries'], window._WATCHDOG_MAX_RETRIES, window._zoom_drive_cap,
        )
