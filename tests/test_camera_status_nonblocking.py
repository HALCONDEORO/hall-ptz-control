# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""GUI transport snapshots must not wait behind worker lifecycle joins."""
import threading
from types import SimpleNamespace
from ptz.visca.manager import CameraManager


def test_transport_snapshot_does_not_wait_for_registry_recovery_lock():
    manager = CameraManager(SimpleNamespace(ip="192.0.2.1", cam_id="81"),
                            SimpleNamespace(ip="192.0.2.2", cam_id="82"))
    manager._workers["192.0.2.1"] = SimpleNamespace(is_connected=True)
    held, release, returned = threading.Event(), threading.Event(), threading.Event()
    result = []
    def recovery():
        with manager._workers_lock:
            held.set()
            assert release.wait(2)
    def status():
        result.append(manager.is_connected("192.0.2.1"))
        result.append(manager.is_connected("192.0.2.99"))
        returned.set()
    recovering = threading.Thread(target=recovery)
    reading = threading.Thread(target=status)
    recovering.start()
    assert held.wait(1)
    try:
        reading.start()
        assert returned.wait(0.15), "GUI status blocked behind camera recovery"
        assert result == [True, False]
    finally:
        release.set()
        recovering.join(2)
        reading.join(2)
