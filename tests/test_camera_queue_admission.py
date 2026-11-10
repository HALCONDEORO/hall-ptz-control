"""Queue acceptance is not execution, and a rejected command must not report OK."""
import queue
import threading
from unittest.mock import Mock

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca import CameraWorker, ViscaCommand


@pytest.mark.parametrize("command,args", [("move", (2, 1)), ("zoom", (3,)), ("home", ()), ("stop_move", ())])
@pytest.mark.parametrize("accepted", [True, False])
def test_adapter_reports_real_admission(command, args, accepted):
    worker = Mock()
    worker.send.return_value = accepted
    worker.send_priority.return_value = accepted
    manager = Mock()
    manager.worker.return_value = worker
    adapter = ViscaCameraAdapter(manager, {1: ("192.0.2.1", "81")})
    result = getattr(adapter, command)("cam1", *args)
    assert result.ok is accepted
    assert ("not confirmed" in result.message) if accepted else ("not queued" in result.message)


@pytest.mark.parametrize("command,args", [("move", (2, 1)), ("zoom", (3,)), ("home", ()), ("stop_move", ()), ("power_on", ())])
def test_unconfigured_camera_never_creates_worker(command, args):
    manager = Mock()
    adapter = ViscaCameraAdapter(manager, {1: ("", "81")})
    assert not getattr(adapter, command)("cam1", *args).ok
    manager.worker.assert_not_called()


@pytest.mark.parametrize("method", ["send", "send_priority", "send_confirmed"])
def test_stopped_worker_rejects_without_waiting_or_queueing(method):
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = "192.0.2.1"
    worker._queue = queue.Queue(maxsize=2)
    worker._shutdown = threading.Event()
    worker._shutdown.set()
    command = ViscaCommand(camera=1, payload=bytes.fromhex("81010604FF"))
    kwargs = {"timeout": 0.01} if method == "send_confirmed" else {}
    assert getattr(worker, method)(command, **kwargs) is False
    assert worker._queue.empty()
