#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# application/network_diagnostics.py — NetworkDiagnosticsService
#
# Comprueba la alcanzabilidad de cámaras y ATEM en la red LAN local.
# Comprueba que la Raspberry Pi está en la subred AV esperada.
# Usa socket TCP — sin dependencias externas.
# Inyectar _probe_fn / _local_ips_fn en tests para evitar I/O de red real.

from __future__ import annotations

import getpass
import ipaddress
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from application.diagnostics_service import CheckResult, Status
from domain.doctor_outcome import CheckCategory
import config as _runtime_config

VISCA_PORT = _runtime_config.VISCA_PORT
# Puerto de control del ATEM (BlackMagic)
ATEM_PORT = 9910

#: systemd units that own the running app's camera sessions (#885).
SYSTEM_UNIT = "khptz-control"
GUI_UNIT = "khptz-gui.service"


def _unit_state(argv: List[str]) -> Optional[str]:
    """Return systemctl's is-active answer for a unit, or None when unknown.

    Only the four definitive states are returned; an error, a missing unit or
    missing systemd yields None so callers can treat the case as "unknown"
    rather than "not running".
    """
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=5,
        )
    except Exception:  # noqa: BLE001 — no systemd, no runuser, timeout: unknown
        return None
    state = result.stdout.strip()
    return state if state in ("active", "activating", "inactive", "failed") else None


def _gui_unit_state_for(user: str) -> Optional[str]:
    """is-active for the desktop user's session-owned GUI unit.

    Returns None when the unit state cannot be determined (neither root nor
    the desktop user is asking).
    """
    getuid = getattr(os, "getuid", None)
    if getuid is not None and getuid() == 0:
        return _unit_state(
            ["runuser", "-u", user, "--", "systemctl", "--user", "is-active", GUI_UNIT]
        )
    try:
        if getpass.getuser() == user:
            return _unit_state(["systemctl", "--user", "is-active", GUI_UNIT])
    except Exception:  # noqa: BLE001
        pass
    return None


def app_may_be_running(resolver=None) -> bool:
    """True whenever the local app may own live camera sessions.

    The VISCA probe in check_cameras() opens a second TCP connection to each
    camera; on single-session models that evicts the app's own worker, which
    is exactly the "camera dropped for no reason" an operator was diagnosing
    when they ran doctor (#144/#145 doctrine). Skipping a probe is always
    safe, so any doubt returns True — probing happens only when the unit
    that owns the GUI is definitively inactive.
    """
    system_state = _unit_state(["systemctl", "is-active", SYSTEM_UNIT])
    if system_state in ("active", "activating"):
        return True
    try:
        from runtime.install_state import GUI_MODE_USER, gui_mode, state_value
    except Exception:  # noqa: BLE001
        return system_state not in ("inactive", "failed")
    if gui_mode(resolver) == GUI_MODE_USER:
        user = state_value("KHPTZ_WIZARD_USER", resolver)
        gui_state = _gui_unit_state_for(user) if user else None
        if gui_state in ("active", "activating"):
            return True
        if system_state is None or gui_state is None:
            return True  # could not prove the app is down
        return False
    # System mode (or a pre-#885 install with no recorded mode): the system
    # unit owns the GUI, and it was already checked above.
    return system_state not in ("inactive", "failed")


@dataclass
class ReachabilityResult:
    host: str
    port: int
    reachable: bool


def _visca_port() -> int:
    """Devuelve el puerto VISCA activo desde la configuración runtime."""
    return _runtime_config.VISCA_PORT


def _tcp_probe(host: str, port: int, timeout: float = 1.0) -> bool:
    """Try to open a TCP connection to *host*:*port*. Return True if successful."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _system_local_ipv4_addresses() -> list[str]:
    """Return all non-loopback IPv4 addresses for this host."""
    try:
        hostname = socket.gethostname()
        _, _, addrs = socket.gethostbyname_ex(hostname)
        return [a for a in addrs if not a.startswith("127.")]
    except OSError:
        return []


class NetworkDiagnosticsService:
    """
    Checks LAN reachability of cameras and ATEM, and verifies the Pi is on
    the expected AV subnet when a network profile is configured.

    Parameters
    ----------
    probe_fn:
        Injectable function ``(host, port) -> bool`` used for reachability checks.
        Defaults to a real TCP probe.  Override in tests to avoid network I/O.
    timeout:
        Timeout in seconds for each probe attempt.
    local_ips_fn:
        Injectable function ``() -> list[str]`` returning this host's IPv4 addresses.
        Defaults to ``_system_local_ipv4_addresses()``. Override in tests.
    app_running_fn:
        Injectable function ``() -> bool`` telling whether the local app may
        own live camera sessions. Defaults to ``app_may_be_running``. While it
        returns True, camera VISCA probes are skipped so a diagnostic cannot
        evict a single-session camera's worker. Override in tests.
    """

    def __init__(
        self,
        probe_fn: Optional[Callable[[str, int], bool]] = None,
        timeout: float = 1.0,
        local_ips_fn: Optional[Callable[[], list[str]]] = None,
        app_running_fn: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._timeout = timeout
        self._probe_fn_injected = probe_fn is not None
        self._probe = probe_fn or (lambda host, port: _tcp_probe(host, port, self._timeout))
        self._local_ips = local_ips_fn or _system_local_ipv4_addresses
        self._app_running = app_running_fn or app_may_be_running

    # ── Pi subnet check ───────────────────────────────────────────────────────

    def check_pi_subnet(self, settings) -> Optional[CheckResult]:
        """
        Check whether this host is on the expected AV subnet.

        Returns None when no av_subnet is configured (check not applicable).
        Returns WARNING (not FAIL) on mismatch — the Pi might be on a dev machine
        or the config may not match the current network yet.
        """
        network = getattr(settings, "network", None)
        if network is None:
            return None  # no network section — not applicable

        av_subnet = getattr(network, "av_subnet", None) or ""
        av_subnet = av_subnet.strip()
        if not av_subnet:
            return None  # subnet not configured — not applicable

        # Parse the subnet; handle malformed values gracefully
        try:
            target_net = ipaddress.IPv4Network(av_subnet, strict=False)
        except ValueError:
            return CheckResult(
                "pi_subnet",
                Status.WARNING,
                f"Network profile has invalid av_subnet '{av_subnet}' — cannot verify Pi subnet",
            )

        local_ips = self._local_ips()
        if not local_ips:
            return CheckResult(
                "pi_subnet",
                Status.WARNING,
                f"No local IPv4 addresses found — cannot verify Pi is on {av_subnet}",
                evidence={"av_subnet": av_subnet},
            )

        matching = [ip for ip in local_ips if ipaddress.IPv4Address(ip) in target_net]
        if matching:
            return CheckResult(
                "pi_subnet",
                Status.OK,
                f"Pi is on expected AV subnet {av_subnet} ({matching[0]})",
                evidence={"av_subnet": av_subnet, "local_ip": matching[0]},
            )

        return CheckResult(
            "pi_subnet",
            Status.WARNING,
            f"Pi does not appear to be on expected AV subnet {av_subnet} "
            f"(local addresses: {', '.join(local_ips)})",
            evidence={"av_subnet": av_subnet, "local_ips": local_ips},
            suggested_action=(
                "Verify the Pi has a static IP in the AV VLAN. "
                "See docs/NETWORK_ARCHITECTURE.md."
            ),
        )

    # ── Camera reachability ───────────────────────────────────────────────────

    def _time_probe(self, host: str, port: int) -> tuple[bool, float]:
        """Probe host:port using _tcp_probe and return (reachable, latency_ms)."""
        t0 = time.perf_counter()
        try:
            reachable = _tcp_probe(host, port, self._timeout)
        except Exception:
            return False, 0.0
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return reachable, elapsed_ms

    def check_cameras(self, settings) -> List[CheckResult]:
        """Return one CheckResult per configured camera.

        While the local app may own live camera sessions, the TCP probe is
        skipped: opening a second connection to the VISCA port can evict a
        single-session camera's worker, so the diagnostic would cause the
        very disconnect it is meant to explain. A camera with no IP still
        FAILs — that is a configuration fact, not a probe result.
        """
        results = []
        probe_allowed = not self._app_running()
        for cam in settings.cameras:
            ip = cam.ip.strip()
            if not ip:
                results.append(CheckResult(
                    f"camera_{cam.id}_reachable", Status.FAIL,
                    f"Camera '{cam.id}': no IP configured",
                ))
                continue
            visca_port = _visca_port()
            if not probe_allowed:
                results.append(CheckResult(
                    f"camera_{cam.id}_reachable",
                    Status.OK,
                    f"Camera '{cam.id}' ({ip}): configured — VISCA probe not "
                    f"run while the app may own the camera session (a second "
                    f"connection can evict it); live state is on the camera card",
                ))
                continue
            if self._probe_fn_injected:
                reachable = self._probe(ip, visca_port)
                latency_ms = 0.0
            else:
                reachable, latency_ms = self._time_probe(ip, visca_port)
            status = Status.OK if reachable else Status.WARNING
            verb = "reachable" if reachable else "unreachable"
            if reachable:
                msg = (
                    f"Camera '{cam.id}' ({ip}): {verb} on VISCA port {visca_port}"
                    f" ({latency_ms:.0f}ms)"
                )
            else:
                msg = f"Camera '{cam.id}' ({ip}): {verb} on VISCA port {visca_port}"
            results.append(CheckResult(
                f"camera_{cam.id}_reachable",
                status,
                msg,
            ))
        return results

    # ── ATEM reachability ─────────────────────────────────────────────────────

    def check_atem(self, settings) -> Optional[CheckResult]:
        """Return a CheckResult for the ATEM if configured and enabled, else None."""
        if not settings.features.atem_enabled:
            return None
        ip = settings.atem.ip.strip()
        if not ip:
            # Enabled with no address is an incomplete configuration the
            # operator must resolve, not a generic warning (#887).
            return CheckResult(
                "atem_reachable",
                Status.WARNING,
                "ATEM enabled but IP not configured",
                suggested_action=(
                    "Set the ATEM IP with `khptz setup --force`, or disable ATEM"
                ),
                category=CheckCategory.CONFIGURATION,
            )
        if not self._probe_fn_injected:
            # ATEM control uses UDP. A TCP connect on the same port says
            # nothing about its health, and an arbitrary UDP send is not a
            # protocol verification either. Do not open a second ATEM session
            # here: the app's monitor owns it and exposes the live state.
            return CheckResult(
                "atem_reachable",
                Status.WARNING,
                f"ATEM ({ip}): UDP control reachability not verified; "
                "a TCP port check is not applicable",
                evidence={"transport": "UDP", "port": ATEM_PORT,
                          "verification_status": "not_run"},
                suggested_action="Check the ATEM connection state in the app.",
                category=CheckCategory.ADVISORY,
            )
        reachable = self._probe(ip, ATEM_PORT)
        status = Status.OK if reachable else Status.WARNING
        verb = "reachable" if reachable else "unreachable"
        return CheckResult(
            "atem_reachable",
            status,
            f"ATEM ({ip}): {verb} on port {ATEM_PORT}",
            suggested_action=(
                None if reachable
                else f"Confirm the ATEM is powered on and reachable at {ip}"
            ),
            # Configured correctly but not answering right now: a hardware or
            # cabling condition, reported independently of configuration.
            category=CheckCategory.OPERATIONAL,
        )
