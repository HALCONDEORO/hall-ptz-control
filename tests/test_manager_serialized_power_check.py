# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Post-assignment checks share the persistent worker's serialized session."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from ptz.visca.manager import CameraManager


def rig(response):
    mgr = CameraManager(SimpleNamespace(ip="192.0.2.1", cam_id="81"),
                        SimpleNamespace(ip="192.0.2.2", cam_id="82"))
    worker = Mock()
    worker.send_inquiry.return_value = response
    mgr._workers["192.0.2.2"] = worker
    return mgr, worker


@pytest.mark.parametrize("reply,expected", [(bytes.fromhex("a05002ff"), True),
    (bytes.fromhex("a05003ff"), True), (bytes.fromhex("a041ff"), False),
    (bytes.fromhex("a06002ff"), False), (b"", False),
    (bytes.fromhex("a05007ff"), False)])
def test_probe_uses_current_address_on_existing_worker(reply, expected):
    mgr, worker = rig(reply)
    assert mgr.check_power_response(2) is expected
    args, kwargs = worker.send_inquiry.call_args
    assert args[0].payload == bytes.fromhex("82090400ff")
    assert args[0].camera == 2
    assert kwargs == {"timeout": 2.0}


def test_missing_worker_does_not_open_any_connection():
    mgr, worker = rig(b"")
    mgr.worker = Mock(side_effect=AssertionError("must not create worker"))
    assert mgr.check_power_response(1) is False
    mgr.worker.assert_not_called()
    worker.send_inquiry.assert_not_called()


def test_replaced_endpoint_cannot_publish_old_probe():
    mgr, worker = rig(b"")
    def reply(*args, **kwargs):
        mgr._cam2_ip = "192.0.2.3"
        return bytes.fromhex("a05002ff")
    worker.send_inquiry.side_effect = reply
    assert mgr.check_power_response(2) is False
