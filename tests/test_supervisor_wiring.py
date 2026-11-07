# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Contract tests for camera/ATEM supervisor wiring without starting threads."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import supervisor_wiring


@pytest.fixture
def wired(monkeypatch):
    supervisor = Mock()
    registrations = {}
    supervisor.registrar.side_effect = lambda name, healthy, restart: registrations.update(
        {name: (healthy, restart)}
    )
    constructor = Mock(return_value=supervisor)
    monkeypatch.setattr(supervisor_wiring, "Supervisor", constructor)
    workers = {
        "camera-one": SimpleNamespace(
            _thread=Mock(), progress_age=Mock(return_value=0), restart=Mock()
        ),
        "camera-two": SimpleNamespace(
            _thread=Mock(), progress_age=Mock(return_value=0), restart=Mock()
        ),
    }
    for worker in workers.values():
        worker._thread.is_alive.return_value = True
    cameras = SimpleNamespace(
        ip_for_key=Mock(side_effect={1: "camera-one", 2: "camera-two"}.__getitem__),
        worker=Mock(side_effect=workers.__getitem__),
    )
    window = SimpleNamespace(
        _cameras=cameras,
        _atem_monitor=SimpleNamespace(healthy=True),
        _restart_atem_monitor=Mock(),
    )
    window._atem_monitor_is_healthy = lambda: window._atem_monitor.healthy
    result = supervisor_wiring.build_supervisor(window)
    return result, supervisor, constructor, registrations, workers, window


def test_registers_each_worker_and_starts_once(wired):
    result, supervisor, constructor, registrations, workers, window = wired
    assert result is supervisor
    constructor.assert_called_once_with()
    assert list(registrations) == [
        "camera_worker_cam1", "camera_worker_cam2", "atem_monitor"
    ]
    assert window._cameras.ip_for_key.call_args_list == [((1,),), ((2,),)]
    assert window._cameras.worker.call_args_list == [(("camera-one",),), (("camera-two",),)]
    supervisor.start.assert_called_once_with()
    assert supervisor.mock_calls[-1][0] == "start"


@pytest.mark.parametrize("camera", [1, 2])
@pytest.mark.parametrize(
    "alive, age_offset, expected",
    [(True, -0.01, True), (True, 0, False), (True, 0.01, False), (False, -1, False)],
)
def test_camera_health_requires_live_thread_and_recent_progress(
    wired, camera, alive, age_offset, expected
):
    _, _, _, registrations, workers, _ = wired
    worker = workers["camera-one" if camera == 1 else "camera-two"]
    worker._thread.is_alive.return_value = alive
    worker.progress_age.return_value = supervisor_wiring.WORKER_STUCK_TIMEOUT_S + age_offset
    healthy, _ = registrations[f"camera_worker_cam{camera}"]
    assert healthy() is expected
    other, _ = registrations[f"camera_worker_cam{3 - camera}"]
    assert other() is True
    if not alive:
        worker.progress_age.assert_not_called()


@pytest.mark.parametrize("camera", [1, 2])
def test_restart_is_bound_to_its_own_camera(wired, camera):
    _, _, _, registrations, workers, _ = wired
    _, restart = registrations[f"camera_worker_cam{camera}"]
    restart()
    workers["camera-one" if camera == 1 else "camera-two"].restart.assert_called_once_with()
    workers["camera-two" if camera == 1 else "camera-one"].restart.assert_not_called()


def test_atem_health_uses_current_monitor_and_own_restart(wired):
    _, _, _, registrations, workers, window = wired
    healthy, restart = registrations["atem_monitor"]
    assert healthy() is True
    window._atem_monitor = SimpleNamespace(healthy=False)
    assert healthy() is False
    window._atem_monitor = SimpleNamespace(healthy=True)
    assert healthy() is True
    restart()
    window._restart_atem_monitor.assert_called_once_with()
    for worker in workers.values():
        worker.restart.assert_not_called()
