"""Shared real TCP scenarios for pytest and the installed self-test command."""
from types import SimpleNamespace

from PyQt5.QtCore import Qt

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.worker import CameraWorker, ViscaCommand
from runtime.selftest_support.visca_simulator import Reply, ScriptedViscaCamera, Step

RECALL = bytes.fromhex('8201043f0201ff')
SCENARIOS = [
    ((Reply(bytes.fromhex('9041ff')), Reply(bytes.fromhex('a051ff'))), False, True),
    ((Reply(bytes.fromhex('9042ff')), Reply(bytes.fromhex('a052ff'), 1.3)), False, True),
    ((Reply(bytes.fromhex('9041ff')),), False, False),
    ((), False, False),
    ((), True, False),
    ((Reply(bytes.fromhex('9041ff9042ff')), Reply(bytes.fromhex('a052ff'))), False, False),
]


def _require(condition, message):
    # Do not use assert: PYTHONOPTIMIZE must not disable the self-test.
    if not condition:
        raise AssertionError(message)


def check_worker_camera(replies, close, expected):
    with ScriptedViscaCamera([Step(RECALL, replies, close)]) as camera:
        worker = CameraWorker(camera.host, camera.port)
        changes = []
        worker.signals.connection_changed.connect(changes.append, Qt.DirectConnection)
        command = ViscaCommand(camera=2, payload=RECALL)
        try:
            result = worker.send_confirmed(command, timeout=1.8)
            _require(result is expected, 'Unexpected confirmed-command outcome')
            _require(camera.received == [RECALL], 'Missing or duplicate recall transmission')
            if expected:
                _require(worker._sock is not None, 'Successful recall lost its TCP session')
                _require(False not in changes, 'Valid delayed recall emitted a false disconnect')
                terminal = 'a051ff' if replies[0].data == bytes.fromhex('9041ff') else 'a052ff'
                _require(command.response.endswith(bytes.fromhex(terminal)),
                         'Recall succeeded without its matching final frame')
            else:
                _require(command.response == b'', 'Failed recall published a successful response')
        finally:
            worker.stop()
            worker._thread.join(2)
            _require(not worker._thread.is_alive(), 'Camera worker failed to stop')


def check_adapter_delayed_recall():
    replies = (Reply(bytes.fromhex('9041ff')), Reply(bytes.fromhex('a051ff'), 1.3))
    with ScriptedViscaCamera([Step(RECALL, replies)]) as camera:
        worker = CameraWorker(camera.host, camera.port)
        changes = []
        worker.signals.connection_changed.connect(changes.append, Qt.DirectConnection)
        adapter = ViscaCameraAdapter(SimpleNamespace(worker=lambda ip: worker),
                                     {2: (camera.host, '82')})
        try:
            _require(adapter.recall_preset('cam2', 1).ok, 'Adapter rejected valid delayed recall')
            _require(camera.received == [RECALL], 'Adapter sent a duplicate or missing recall')
            _require(worker._sock is not None, 'Adapter recall retired the TCP session')
            _require(False not in changes, 'Adapter recall caused a false disconnect')
        finally:
            worker.stop()
            worker._thread.join(2)
            _require(not worker._thread.is_alive(), 'Adapter worker failed to stop')


def run_checks():
    names = ('mixed_socket1', 'delayed_socket2', 'ack_without_completion',
             'silent_open_socket', 'peer_eof', 'two_ack_wrong_socket')
    scenarios = [(name, lambda values=values: check_worker_camera(*values))
                 for name, values in zip(names, SCENARIOS)]
    scenarios.append(('adapter_delayed_recall', check_adapter_delayed_recall))
    checks = []
    for name, scenario in scenarios:
        try:
            scenario()
            checks.append({'name': 'visca_' + name, 'passed': True,
                           'detail': 'Loopback worker/adapter assertions passed'})
        except Exception as exc:
            checks.append({'name': 'visca_' + name, 'passed': False,
                           'detail': str(exc) or type(exc).__name__})
    return checks
