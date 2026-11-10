"""Real TCP worker regressions against the dependency-free scripted camera."""
from types import SimpleNamespace

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.worker import CameraWorker, ViscaCommand
from runtime.selftest_support.visca_simulator import Reply, ScriptedViscaCamera, Step


RECALL = bytes.fromhex('8201043f0201ff')


@pytest.mark.parametrize('replies,close,expected', [
    ((Reply(bytes.fromhex('9041ff')), Reply(bytes.fromhex('a051ff'))), False, True),
    ((Reply(bytes.fromhex('9042ff')), Reply(bytes.fromhex('a052ff'), 1.3)), False, True),
    ((Reply(bytes.fromhex('9041ff')),), False, False),
    ((), False, False),
    ((), True, False),
    # First ACK socket is binding. A second ACK must not legitimize a
    # different terminal socket, even when its source header is allowed.
    ((Reply(bytes.fromhex('9041ff9042ff')), Reply(bytes.fromhex('a052ff'))), False, False),
])
def test_scripted_worker_camera(replies, close, expected):
    with ScriptedViscaCamera([Step(RECALL, replies, close)]) as camera:
        worker = CameraWorker(camera.host, camera.port)
        command = ViscaCommand(camera=2, payload=RECALL)
        try:
            result = worker.send_confirmed(command, timeout=1.8)
            assert result is expected
            assert camera.received == [RECALL]
            if expected:
                assert worker._sock is not None
                assert command.response.endswith(bytes.fromhex('a051ff') if replies[0].data == bytes.fromhex('9041ff') else bytes.fromhex('a052ff'))
            else:
                # An expired caller can wake up just before the worker retires
                # its cancelled read; stop below owns deterministic cleanup.
                assert command.response == b''
        finally:
            worker.stop()
            worker._thread.join(2)
            assert not worker._thread.is_alive()


def test_adapter_delayed_recall_uses_same_persistent_session():
    with ScriptedViscaCamera([Step(RECALL, (
            Reply(bytes.fromhex('9041ff')), Reply(bytes.fromhex('a051ff'), 1.3)))]) as camera:
        worker = CameraWorker(camera.host, camera.port)
        adapter = ViscaCameraAdapter(SimpleNamespace(worker=lambda ip: worker),
                                     {2: (camera.host, '82')})
        try:
            assert adapter.recall_preset('cam2', 1).ok
            assert camera.received == [RECALL]
            assert worker._sock is not None
        finally:
            worker.stop()
