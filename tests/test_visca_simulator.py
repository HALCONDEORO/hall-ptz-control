"""Tests of the test camera itself, no Qt and no physical device."""
import socket

from tests.helpers.visca_simulator import Reply, ScriptedViscaCamera, Step


COMMAND = bytes.fromhex('8201043f0201ff')


def test_mixed_headers_and_recorded_command():
    with ScriptedViscaCamera([Step(COMMAND, (
            Reply(bytes.fromhex('9042ff')), Reply(bytes.fromhex('a052ff'), delay=0.02)))]) as camera:
        with socket.create_connection((camera.host, camera.port), timeout=1) as connection:
            connection.sendall(COMMAND)
            response = b''
            while len(response) < 6:
                response += connection.recv(64)
        assert response == bytes.fromhex('9042ffa052ff')
        assert camera.received == [COMMAND]
    assert not camera.thread.is_alive()


def test_disconnect_then_reconnect_consumes_next_step():
    with ScriptedViscaCamera([Step(COMMAND, close=True),
                              Step(COMMAND, (Reply(bytes.fromhex('a051ff')),))]) as camera:
        with socket.create_connection((camera.host, camera.port), timeout=1) as first:
            first.sendall(COMMAND)
            assert first.recv(64) == b''
        with socket.create_connection((camera.host, camera.port), timeout=1) as second:
            second.sendall(COMMAND)
            assert second.recv(64) == bytes.fromhex('a051ff')
        assert camera.received == [COMMAND, COMMAND]


def test_silent_open_socket_stops_promptly_without_waiting_for_peer():
    with ScriptedViscaCamera([Step(COMMAND)]) as camera:
        connection = socket.create_connection((camera.host, camera.port), timeout=1)
        try:
            connection.sendall(COMMAND)
            assert camera.wait_received(1, timeout=1)
        finally:
            connection.close()
    assert not camera.thread.is_alive()
