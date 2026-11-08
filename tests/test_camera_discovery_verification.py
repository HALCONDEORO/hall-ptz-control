"""No real devices or network: every socket/discovery collaborator is fake."""
import socket

import pytest

from adapters import camera_identity_probe as probe
from application import camera_discovery_verification as verification


class FakeSocket:
    chunks = []
    sent = []
    error = None

    def __init__(self, *args):
        self.remaining = list(self.chunks)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def settimeout(self, timeout):
        assert 0 < timeout <= 0.6

    def connect(self, address):
        if self.error:
            raise self.error

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, limit):
        if self.remaining:
            return self.remaining.pop(0)
        return b''


@pytest.fixture(autouse=True)
def fake_network(monkeypatch):
    FakeSocket.sent = []
    FakeSocket.error = None
    FakeSocket.chunks = []
    monkeypatch.setattr(probe.socket, 'socket', FakeSocket)


@pytest.mark.parametrize('chunks', [
    [b'\x90\x50\x02\xff'], [b'\x90\x50\x03\xff'],
    [b'\x90', b'\x50\x02', b'\xff'],
    [b'\x90\x41\xff\x90\x50\x02\xff'],
    [b'\x90\x41\xff', b'\x90\x50\x03\xff'],
])
def test_recognises_only_power_inquiry(chunks):
    FakeSocket.chunks = chunks
    assert probe.probe_visca_identity('192.0.2.10', 5678)
    assert FakeSocket.sent == [bytes.fromhex('81090400ff')]


@pytest.mark.parametrize('chunks', [
    [], [b'HTTP/1.1 200 OK\r\n'], [b'\x90\x41\xff'],
    [b'\x90\x50\x02'], [b'\x90\x50\x04\xff'],
    [b'\x90\x60\x02\xff'], [b'\x91\x50\x02\xff'],
    [b'garbage\x90\x50\x02\xff'], [b'\x90\x50\x02\x00\xff'],
    [b'x' * 64],
])
def test_open_port_not_recognition(chunks):
    FakeSocket.chunks = chunks
    assert not probe.probe_visca_identity('192.0.2.10', 5678)


@pytest.mark.parametrize('error', [socket.timeout(), OSError('refused')])
def test_network_failure_is_unrecognised(error):
    FakeSocket.error = error
    assert not probe.probe_visca_identity('192.0.2.10', 5678)


@pytest.mark.parametrize('prefix', ['', '192.168', 'a.b.c', '192.168.300',
                                    '192.168.1.0/24', '127.0.0', '224.0.0', '0.0.0'])
def test_invalid_scope_rejected(prefix):
    with pytest.raises(ValueError):
        verification.validate_subnet(prefix)


def test_candidates_keep_separate_facts_and_selected_scope(monkeypatch):
    from application import camera_discovery
    seen = []
    monkeypatch.setattr(camera_discovery, 'discover_cameras',
                        lambda prefix: seen.append(prefix) or
                        ['192.0.2.11', '192.0.2.10', '192.0.2.11', '198.51.100.1'])
    monkeypatch.setattr(probe, 'probe_visca_identity', lambda ip, port: ip.endswith('10'))
    found = verification.discover_and_verify('192.0.2')
    assert seen == ['192.0.2']
    assert [(c.ip, c.recognised) for c in found] == [('192.0.2.10', True), ('192.0.2.11', False)]
    assert 'recognised' in found[0].status
    assert 'not recognised' in found[1].status
