"""A TCP listener is neither necessary nor sufficient evidence of an ATEM."""
import socket
from unittest.mock import Mock

import pytest

from application import camera_discovery as discovery


def test_discovery_reports_unsupported_without_scanning(monkeypatch):
    tcp = Mock(return_value=['192.0.2.1'])
    monkeypatch.setattr(discovery, 'tcp_scan', tcp)
    with pytest.raises(NotImplementedError, match='discovery unsupported'):
        discovery.discover_atem_switchers('192.0.2')
    tcp.assert_not_called()


def test_udp_listener_can_exist_with_tcp_closed():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        udp.bind(('127.0.0.1', 0))
        port = udp.getsockname()[1]
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
            assert tcp.connect_ex(('127.0.0.1', port)) != 0
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(b'UDP control transport', ('127.0.0.1', port))
        udp.settimeout(1)
        assert udp.recv(128) == b'UDP control transport'


def test_tab_does_not_offer_unverified_discovery_or_tcp_scan(monkeypatch):
    from tests.config_pages_harness import button_named, has_text, make_harness, panel_layout
    from ui.config_pages.atem_tab import build_atem_tab
    dialog, window, layout = make_harness()
    build_atem_tab(dialog, layout, window, False, False, panel_layout)
    assert not button_named(layout, 'Discover switchers').isEnabled()
    assert not button_named(layout, 'Scan').isEnabled()
    assert has_text(layout, 'enter the switcher IP manually')
    assert button_named(layout, 'Reconnect ATEM').isEnabled()
