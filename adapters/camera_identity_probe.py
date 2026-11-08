"""Bounded, read-only VISCA power inquiry. Never sends motion commands."""
from __future__ import annotations

import ipaddress
import socket
import time

POWER_INQUIRY = bytes.fromhex('81090400ff')


def probe_visca_identity(ip: str, port: int, timeout: float = 0.6) -> bool:
    """Recognise a standard address-1 VISCA power reply, not a model/brand.

    ACK alone, arbitrary bytes and VISCA errors are not identification. TCP may
    split or coalesce frames. No retries, broadcast, power change or movement.
    Other protocols/addresses remain unrecognised, not necessarily incompatible.
    """
    address = ipaddress.IPv4Address(ip)
    if address.is_multicast or address.is_unspecified or int(address) == 0xffffffff:
        raise ValueError('A unicast IPv4 address is required')
    if not 1 <= port <= 65535 or timeout <= 0:
        raise ValueError('Invalid probe port or timeout')
    deadline = time.monotonic() + timeout
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((ip, port))
            sock.settimeout(max(0.001, deadline - time.monotonic()))
            sock.sendall(POWER_INQUIRY)
            pending = b''
            received = 0
            while received < 64:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                sock.settimeout(remaining)
                chunk = sock.recv(64 - received)
                if not chunk:
                    return False
                received += len(chunk)
                pending += chunk
                while b'\xff' in pending:
                    frame, pending = pending.split(b'\xff', 1)
                    if frame in (b'\x90\x50\x02', b'\x90\x50\x03'):
                        return True
                    if frame not in (b'\x90\x41', b'\x90\x42'):
                        return False
    except (OSError, ValueError):
        return False
    return False
