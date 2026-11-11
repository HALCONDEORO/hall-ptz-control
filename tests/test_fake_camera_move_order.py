"""Tests for FakeCamera move-ordering guarantees (adapters/fake_camera.py).

A real VISCA camera obeys "last command wins": a second recall supersedes
the first, and stop()/standby() cancel the move in progress so the camera
never reports arriving at a preset it was stopped away from. The fake must
reproduce that contract, or demo/simulation mode shows preset state no real
camera could produce.
"""
from __future__ import annotations

import threading
import time

from adapters.fake_camera import FakeCamera


def _cam(move_delay: float) -> FakeCamera:
    return FakeCamera(camera_id="platform", role="platform", move_delay_s=move_delay)


class TestLastCommandWins:
    def test_out_of_order_completion_keeps_latest_preset(self, monkeypatch):
        """Two recalls whose simulated moves finish out of order must still
        leave the LAST requested preset as current — a real camera abandons
        the first move when the second recall arrives."""
        gate = threading.Event()
        calls: list[float] = []
        calls_lock = threading.Lock()

        def _reordered_sleep(_seconds: float) -> None:
            with calls_lock:
                calls.append(_seconds)
                first = len(calls) == 1
            if first:
                # First move to "arrive" waits until the second move is done,
                # so the stale arrival lands last.
                gate.wait(timeout=5.0)
            else:
                gate.set()

        import adapters.fake_camera as fake_camera_module

        monkeypatch.setattr(fake_camera_module.time, "sleep", _reordered_sleep)
        cam = _cam(move_delay=1.0)
        cam.recall_preset(3)
        cam.recall_preset(9)
        deadline = time.monotonic() + 5.0
        while cam.get_status().moving and time.monotonic() < deadline:
            time.sleep(0.01)
        assert cam.get_status().current_preset == 9

    def test_sequential_recalls_settle_on_latest(self):
        cam = _cam(move_delay=0.05)
        cam.recall_preset(2)
        cam.recall_preset(7)
        time.sleep(0.3)
        status = cam.get_status()
        assert status.moving is False
        assert status.current_preset == 7


class TestStopCancelsPendingArrival:
    def test_stop_prevents_late_arrival(self):
        """stop() before the move completes: the camera never reaches the
        preset, so current_preset must stay unset once the timer fires."""
        cam = _cam(move_delay=0.05)
        cam.recall_preset(4)
        cam.stop()
        time.sleep(0.3)
        status = cam.get_status()
        assert status.moving is False
        assert status.current_preset is None

    def test_standby_prevents_late_arrival(self):
        """standby() mid-move cancels the pending arrival as well."""
        cam = _cam(move_delay=0.05)
        cam.power_on()
        cam.recall_preset(6)
        cam.standby()
        time.sleep(0.3)
        status = cam.get_status()
        assert status.moving is False
        assert status.current_preset is None

    def test_recall_after_stop_still_arrives(self):
        """The generation guard must not wedge the camera: a recall issued
        after stop() arrives normally."""
        cam = _cam(move_delay=0.05)
        cam.recall_preset(4)
        cam.stop()
        cam.recall_preset(8)
        time.sleep(0.3)
        status = cam.get_status()
        assert status.moving is False
        assert status.current_preset == 8
