"""Coalescing belongs to a VISCA command address, not the TCP endpoint."""
import queue
import threading

import pytest

from ptz.visca.worker import CameraWorker, ViscaCommand


@pytest.mark.parametrize('body', ['01060105040103ff', '01040723ff'])
def test_coalescing_preserves_other_visca_address(body):
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._queue = queue.Queue(maxsize=20)
    worker._shutdown = threading.Event()
    first = ViscaCommand(camera=1, payload=bytes.fromhex('81' + body), coalesce=True)
    second = ViscaCommand(camera=2, payload=bytes.fromhex('82' + body), coalesce=True)
    assert worker.send(first)
    assert worker.send(second)
    assert list(worker._queue.queue) == [first, second]


@pytest.mark.parametrize('body', ['01060105040103ff', '01040723ff'])
def test_coalescing_same_address_still_replaces_even_for_logical_alias(body):
    worker = CameraWorker.__new__(CameraWorker)
    worker.ip = '192.0.2.1'
    worker._queue = queue.Queue(maxsize=20)
    worker._shutdown = threading.Event()
    first = ViscaCommand(camera=1, payload=bytes.fromhex('81' + body), coalesce=True)
    replacement = ViscaCommand(camera=2, payload=bytes.fromhex('81' + body), coalesce=True)
    assert worker.send(first)
    assert worker.send(replacement)
    assert list(worker._queue.queue) == [replacement]
