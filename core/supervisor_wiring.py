#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# core/supervisor_wiring.py — Cableado del Supervisor de threads de la app
# (extraído de MainWindow para mantener ui/main_window.py dentro de su
# presupuesto anti-god-object, ver tests/test_ui_god_object_budget.py).

from __future__ import annotations

from config import WORKER_STUCK_TIMEOUT_S
from core.supervisor import Supervisor


def build_supervisor(main_window) -> Supervisor:
    """Watch the currently configured camera workers and active ATEM monitor."""
    sup = Supervisor()
    for key in (1, 2):
        sup.registrar(
            f"camera_worker_cam{key}",
            lambda key=key: main_window._cameras.worker_is_healthy(
                key, WORKER_STUCK_TIMEOUT_S),
            lambda key=key: main_window._cameras.restart_worker(key),
        )
    # El lambda evalúa main_window._atem_monitor en tiempo de ejecución, por lo
    # que siempre comprueba la instancia activa incluso tras un reinicio.
    sup.registrar(
        "atem_monitor",
        main_window._atem_monitor_is_healthy,
        main_window._restart_atem_monitor,
    )
    sup.start()
    return sup
