#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# ui/camera_led_wiring.py — LED ámbar de (re)conexión de cámara
# (extraído de MainWindow — presupuesto anti-god-object).

from __future__ import annotations

from domain.camera_state import CameraConnectionState


def wire_connecting_led(main_window, worker) -> None:
    """LED ámbar mientras el worker intenta (re)conectar con la cámara.

    Se cablea para CADA worker, igual que connection_changed, para que el
    indicador siga al worker actual tras un cambio de IP.
    """
    def _on_state_changed(state, _ip=worker.ip) -> None:
        if not main_window._cameras.worker_is_current(worker):
            return
        try:
            cam_key = main_window._cameras.cam_key(_ip)
        except ValueError:
            return
        (main_window.Cam1 if cam_key == 1 else main_window.Cam2).set_connecting(
            worker._connection_state is CameraConnectionState.CONNECTING)

    worker.signals.connection_state_changed.connect(_on_state_changed)


def wire_camera_worker(main_window, worker) -> None:
    """Discard queued signals from retired transports, even after IP reuse."""
    def error(ip, cmd_type):
        if main_window._cameras.worker_is_current(worker):
            main_window._on_visca_speed_error(ip, cmd_type)

    def connected(ok):
        if main_window._cameras.worker_is_current(worker):
            # Queued bool may predate a reconnect by this same worker.
            ok = main_window._cameras.is_connected(worker.ip)
            main_window._on_cam_connected(ok, worker.ip)
            main_window._on_cam_connection_changed(ok, worker.ip)

    worker.signals.visca_error.connect(error)
    worker.signals.connection_changed.connect(connected)
    wire_connecting_led(main_window, worker)
