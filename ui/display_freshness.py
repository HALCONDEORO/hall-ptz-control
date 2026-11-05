# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Drop camera display updates that were queued before a reconfiguration.

Display queries (zoom, AE mode) run on worker threads and publish their result
to the Qt thread through queued calls. The adapter checks the camera generation
before publishing, but a queued call can still run after the camera was
reconfigured or after the operator selected the other camera. These helpers let
the Qt side capture a ticket when the query starts and re-check it on delivery.

No Qt imports here, so the logic can be tested without a QApplication.
"""
from __future__ import annotations

from typing import Any


def capture_display_generation(port: Any, cam_key: int) -> int:
    """Generation of *cam_key* now; 0 when the port does not track generations."""
    getter = getattr(port, "display_generation", None)
    if not callable(getter):
        return 0
    try:
        return int(getter(cam_key))
    except (TypeError, ValueError):
        return 0


def display_update_is_current(
    port: Any, cam_key: int, generation: int, selected_cam_key: int
) -> bool:
    """True when a queued display update still applies to what is on screen.

    It applies only if the camera was not reconfigured since the ticket was
    captured and *cam_key* is still the camera the operator has selected.
    """
    if cam_key != selected_cam_key:
        return False
    return capture_display_generation(port, cam_key) == generation
