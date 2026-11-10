# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Configured endpoints must not receive discovery connections."""
from unittest.mock import Mock
from application import camera_discovery as discovery
from application import camera_discovery_verification as verification
from adapters import camera_identity_probe


def test_tcp_scan_skips_configured_hosts_before_connect(monkeypatch):
    seen = []
    monkeypatch.setattr(discovery, "_tcp_connect", lambda ip, *args: seen.append(ip) or True)
    found = discovery.tcp_scan("192.0.2", workers=1, exclude_ips=("192.0.2.1", "192.0.2.2"))
    assert "192.0.2.1" not in seen + found
    assert "192.0.2.2" not in seen + found
    assert len(seen) == 252


def test_arp_cannot_reintroduce_configured_endpoints(monkeypatch):
    seen = []
    monkeypatch.setattr(discovery, "tcp_scan", lambda subnet, **kwargs: ["192.0.2.1", "192.0.2.3"])
    monkeypatch.setattr(discovery, "arp_scan", lambda subnet: ["192.0.2.1", "192.0.2.2", "192.0.2.4"])
    monkeypatch.setattr(discovery, "_tcp_connect", lambda ip: seen.append(ip) or True)
    assert discovery.discover_cameras("192.0.2", exclude_ips=("192.0.2.1", "192.0.2.2")) == ["192.0.2.3", "192.0.2.4"]
    assert seen == ["192.0.2.4"]


def test_identity_stage_rechecks_exclusion_before_power_inquiry(monkeypatch):
    scan = Mock(return_value=["192.0.2.1", "192.0.2.2", "192.0.2.3"])
    probe = Mock(return_value=True)
    monkeypatch.setattr(discovery, "discover_cameras", scan)
    monkeypatch.setattr(camera_identity_probe, "probe_visca_identity", probe)
    result = verification.discover_and_verify("192.0.2", exclude_ips=("192.0.2.1", "192.0.2.2"))
    assert [item.ip for item in result] == ["192.0.2.3"]
    scan.assert_called_once_with("192.0.2", exclude_ips={"192.0.2.1", "192.0.2.2"})
    probe.assert_called_once_with("192.0.2.3", discovery.VISCA_PORT)
