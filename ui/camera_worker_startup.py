# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Startup creates transport sessions only for installed camera endpoints."""


def start_configured_camera_workers(manager):
    for key in (1, 2):
        ip = manager.ip_for_key(key)
        if ip:
            manager.worker(ip)
