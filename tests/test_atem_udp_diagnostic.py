"""TCP reachability cannot establish the state of a UDP ATEM endpoint."""
import socket
from types import SimpleNamespace
from unittest.mock import patch

from application.diagnostics_service import Status
from application.network_diagnostics import NetworkDiagnosticsService, _tcp_probe


def test_udp_endpoint_is_not_reported_unreachable_by_tcp():
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(('127.0.0.1', 0))
    receiver.settimeout(1)
    host, port = receiver.getsockname()
    try:
        sender.sendto(b'local transport fixture', (host, port))
        assert receiver.recv(128) == b'local transport fixture'
        assert not _tcp_probe(host, port, timeout=0.05)
        settings = SimpleNamespace(features=SimpleNamespace(atem_enabled=True),
                                   atem=SimpleNamespace(ip=host))
        with patch('application.network_diagnostics.ATEM_PORT', port), \
             patch('application.network_diagnostics._tcp_probe') as tcp:
            tcp.return_value = False
            result = NetworkDiagnosticsService().check_atem(settings)
        tcp.assert_not_called()
        assert result.status is Status.WARNING
        assert result.evidence['verification_status'] == 'not_run'
        assert 'UDP' in result.message
        assert 'unreachable' not in result.message
    finally:
        sender.close()
        receiver.close()
