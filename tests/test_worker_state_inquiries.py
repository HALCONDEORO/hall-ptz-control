"""Display inquiries share the worker connection with movement commands."""
import socket
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from adapters.visca_camera_adapter import ViscaCameraAdapter
from ptz.visca.worker import CameraWorker, ViscaCommand


def test_adapter_never_opens_a_parallel_query_socket(monkeypatch):
    worker = Mock()
    worker.send_inquiry.side_effect = [
        b"\x90\x50\x02\x00\x00\x00\xff",  # zoom 0x2000
        b"\x90\x50\x00\xff",  # automatic exposure
        b"\x90\x50\x00\x00\x00\x09\xff",  # compensation +2
    ]
    manager = Mock()
    manager.worker.return_value = worker
    adapter = ViscaCameraAdapter(manager)
    socket_factory = Mock(side_effect=AssertionError("parallel socket"))
    monkeypatch.setattr("adapters.visca_camera_adapter.socket.socket", socket_factory)
    assert adapter._query_zoom("192.0.2.1", "81") == 0x2000
    assert adapter._query_ae_and_exp_comp("192.0.2.1", "81") == ("auto", 2)
    assert [c.args[0].payload for c in worker.send_inquiry.call_args_list] == [
        bytes.fromhex("81090447ff"), bytes.fromhex("81090439ff"),
        bytes.fromhex("8109044eff"),
    ]
    socket_factory.assert_not_called()


@pytest.mark.parametrize("mode", [3, 13])
def test_manual_or_bright_mode_skips_compensation(mode):
    worker = Mock()
    worker.send_inquiry.return_value = bytes([0x90, 0x50, mode, 0xff])
    adapter = ViscaCameraAdapter(SimpleNamespace(worker=lambda ip: worker))
    assert adapter._query_ae_and_exp_comp("192.0.2.1", "81") == (
        "manual" if mode == 3 else "bright", None,
    )
    assert worker.send_inquiry.call_count == 1


def test_unconfigured_query_does_not_create_worker():
    manager = Mock()
    adapter = ViscaCameraAdapter(manager)
    assert adapter._query_zoom("", "81") is None
    assert adapter._query_ae_and_exp_comp(" ", "81") == (None, None)
    manager.worker.assert_not_called()


@pytest.mark.parametrize("admitted", [False, True])
def test_inquiry_returns_data_only_after_confirmation(admitted):
    # Isolate the response handoff contract without starting a network thread.
    worker = object.__new__(CameraWorker)
    cmd = ViscaCommand(1, bytes.fromhex("81090447ff"), response=b"old")

    def confirmed(command, timeout):
        assert command.response == b""
        command.response = b"new"
        return admitted

    worker.send_confirmed = confirmed
    assert worker.send_inquiry(cmd, 0.1) == (b"new" if admitted else b"")


def test_real_worker_reuses_one_tcp_session_for_commands_and_inquiries():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    listener.settimeout(2)
    received = []
    failures = []
    replies = [b"\x90\x51\xff", b"\x90\x50\x02\x00\x00\x00\xff",
               b"\x90\x51\xff"]

    def serve():
        try:
            with listener.accept()[0] as connection:
                connection.settimeout(2)
                pending = b""
                for reply in replies:
                    while b"\xff" not in pending:
                        chunk = connection.recv(64)
                        if not chunk:
                            raise AssertionError("worker replaced the control session")
                        pending += chunk
                    frame, pending = pending.split(b"\xff", 1)
                    received.append(frame + b"\xff")
                    connection.sendall(reply)
        except Exception as exc:
            failures.append(exc)

    server = threading.Thread(target=serve)
    server.start()
    worker = CameraWorker("127.0.0.1", listener.getsockname()[1])
    try:
        before = ViscaCommand(1, bytes.fromhex("8101043802ff"))
        inquiry = ViscaCommand(1, bytes.fromhex("81090447ff"))
        after = ViscaCommand(1, bytes.fromhex("8101043803ff"))
        assert worker.send_confirmed(before, 2)
        assert worker.send_inquiry(inquiry, 2) == replies[1]
        assert worker.send_confirmed(after, 2)
        server.join(3)
        assert not server.is_alive()
        assert not failures
        assert received == [before.payload, inquiry.payload, after.payload]
    finally:
        worker.stop()
        listener.close()
        server.join(3)


def test_timed_out_queued_inquiry_is_cancelled_without_response():
    worker = object.__new__(CameraWorker)
    worker.ip = "192.0.2.1"
    queued = []
    worker.send = lambda cmd: queued.append(cmd) or True
    cmd = ViscaCommand(1, bytes.fromhex("81090447ff"))
    assert worker.send_inquiry(cmd, 0.01) == b""
    assert queued == [cmd]
    assert cmd.cancelled.is_set()
    assert worker._command_outdated(cmd)


def test_emergency_stop_interrupts_a_pending_inquiry():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    listener.settimeout(3)
    inquiry_sent = threading.Event()
    stop_seen = threading.Event()
    stop_done = threading.Event()
    failures = []
    stop_payload = bytes.fromhex("8101060100000303ff")

    def serve():
        try:
            with listener.accept()[0] as connection:
                connection.settimeout(3)
                assert connection.recv(64) == bytes.fromhex("81090447ff")
                inquiry_sent.set()
                # STOP must retire this interrupted session; no stale data is reused.
                assert connection.recv(64) == b""
            with listener.accept()[0] as connection:
                connection.settimeout(3)
                assert connection.recv(64) == stop_payload
                stop_seen.set()
                connection.sendall(b"\x90\x51\xff")
        except Exception as exc:
            failures.append(exc)

    server = threading.Thread(target=serve)
    server.start()
    worker = CameraWorker("127.0.0.1", listener.getsockname()[1])
    results = []
    caller = threading.Thread(target=lambda: results.append(worker.send_inquiry(
        ViscaCommand(1, bytes.fromhex("81090447ff")), timeout=3,
    )))
    caller.start()
    try:
        assert inquiry_sent.wait(2)
        assert worker.send_priority(ViscaCommand(1, stop_payload, on_success=stop_done.set))
        assert stop_seen.wait(2)
        assert stop_done.wait(2)
        caller.join(2)
        server.join(2)
        assert not caller.is_alive()
        assert not server.is_alive()
        assert not failures
        assert results == [b""]
    finally:
        worker.stop()
        listener.close()
        caller.join(4)
        server.join(4)
