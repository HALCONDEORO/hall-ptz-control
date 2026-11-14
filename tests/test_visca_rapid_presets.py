"""Rapid recall/queue regression over real loopback TCP, never hall hardware.

The first camera Completion is deliberately slower than VISCA_READ_TIMEOUT.
Further recalls enter while it is in flight, rather than serializing callers
and accidentally testing only a sequence of individual button presses.
"""
from concurrent.futures import ThreadPoolExecutor
import threading
from types import SimpleNamespace

from PyQt5.QtCore import Qt
import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from config import CAMERA_QUEUE_MAXSIZE
from ptz.visca.worker import CameraWorker, ViscaCommand
from runtime.selftest_support.visca_simulator import Reply, ScriptedViscaCamera, Step


def _recall(address, preset):
    return bytes((address, 1, 4, 0x3F, 2, preset, 0xFF))


class _GatedCompletion:
    """Do not complete the first command before every burst admission happened."""
    delay = 1.15

    def __init__(self, data, admissions_complete):
        self._data = data
        self._admissions_complete = admissions_complete

    @property
    def data(self):
        assert self._admissions_complete.wait(3), 'Burst producers failed to finish'
        return self._data


def _steps(address, count, admissions_complete):
    return [Step(_recall(address, index + 1), (
        Reply(bytes((0x90, 0x41 + index % 2, 0xFF))),
        # Both direct-IP 90 and the configured addressed terminal are valid.
        (_GatedCompletion(bytes((((address - 0x80 + 8) << 4), 0x51, 0xFF)),
                          admissions_complete) if index == 0 else
         Reply(bytes((((address - 0x80 + 8) << 4), 0x51 + index % 2, 0xFF)), 0.005)),
    )) for index in range(count)]


@pytest.mark.parametrize('address', [0x81, 0x82])
def test_concurrent_adapter_preset_burst_keeps_original_tcp_session(address):
    count = 8
    admissions_complete = threading.Event()
    with ScriptedViscaCamera(_steps(address, count, admissions_complete)) as camera:
        worker = CameraWorker(camera.host, camera.port)
        changes = []
        worker.signals.connection_changed.connect(changes.append, Qt.DirectConnection)
        adapter = ViscaCameraAdapter(SimpleNamespace(worker=lambda ip: worker),
                                     {address - 0x80: (camera.host, f'{address:02x}')})
        original_send = worker.send
        admissions = [threading.Event() for _ in range(count)]

        def observed_send(command):
            accepted = original_send(command)
            admissions[command.payload[-2] - 1].set()
            return accepted

        worker.send = observed_send
        try:
            with ThreadPoolExecutor(max_workers=count) as executor:
                first = executor.submit(adapter.recall_preset, f'cam{address - 0x80}', 1)
                assert camera.wait_received(1)
                original_socket = worker._sock
                futures = [first]
                for preset in range(2, count + 1):
                    futures.append(executor.submit(adapter.recall_preset,
                                                   f'cam{address - 0x80}', preset))
                    assert admissions[preset - 1].wait(1), 'Burst was not actually queued'
                admissions_complete.set()
                assert all(future.result(timeout=5).ok for future in futures)
            assert camera.received == [_recall(address, preset)
                                       for preset in range(1, count + 1)]
            assert worker._sock is original_socket
            assert False not in changes
            assert worker._thread.is_alive()
        finally:
            admissions_complete.set()
            worker.stop()
            assert not worker._thread.is_alive()


@pytest.mark.parametrize('address', [0x81, 0x82])
def test_full_preset_queue_rejects_excess_without_disconnect_or_ghost_send(address):
    # One in flight + the actual bounded queue. Do not enlarge it for the test.
    accepted_count = CAMERA_QUEUE_MAXSIZE + 1
    count = accepted_count + 3
    admissions_complete = threading.Event()
    with ScriptedViscaCamera(_steps(address, accepted_count, admissions_complete)) as camera:
        worker = CameraWorker(camera.host, camera.port)
        changes = []
        worker.signals.connection_changed.connect(changes.append, Qt.DirectConnection)
        admissions = [threading.Event() for _ in range(count)]
        accepted = {}
        original_send = worker.send

        def observed_send(command):
            index = command.payload[-2] - 1
            accepted[index] = original_send(command)
            admissions[index].set()
            return accepted[index]

        worker.send = observed_send
        commands = [ViscaCommand(camera=address - 0x80,
                                 payload=_recall(address, index + 1))
                    for index in range(count)]
        try:
            with ThreadPoolExecutor(max_workers=count) as executor:
                futures = [executor.submit(worker.send_confirmed, commands[0], 4)]
                assert camera.wait_received(1)
                original_socket = worker._sock
                for index in range(1, count):
                    futures.append(executor.submit(worker.send_confirmed, commands[index], 4))
                    assert admissions[index].wait(1)
                admissions_complete.set()
                results = [future.result(timeout=5) for future in futures]
            assert results == [True] * accepted_count + [False] * 3
            assert [accepted[index] for index in range(count)] == results
            assert camera.received == [command.payload for command in commands[:accepted_count]]
            assert all(command.response for command in commands[:accepted_count])
            assert all(not command.response and command.sent_at == 0
                       for command in commands[accepted_count:])
            assert worker._sock is original_socket
            assert False not in changes
            assert worker._queue.empty()
        finally:
            admissions_complete.set()
            worker.stop()
            assert not worker._thread.is_alive()
