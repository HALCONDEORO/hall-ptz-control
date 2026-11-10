"""Discovery presentation facts; an open TCP port is not camera recognition."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import ipaddress

from config import VISCA_PORT


@dataclass(frozen=True)
class CameraCandidate:
    ip: str
    recognised: bool

    @property
    def status(self) -> str:
        return ('VISCA reply recognised (power inquiry)' if self.recognised
                else 'TCP port accessible; camera not recognised')


def validate_subnet(subnet: str) -> str:
    """Only explicit IPv4 /24 prefixes: do not silently scan a fallback network."""
    network = ipaddress.IPv4Network(subnet.strip() + '.0/24', strict=True)
    if network.is_multicast or network.network_address.is_unspecified or network.is_loopback or network.is_reserved:
        raise ValueError('Choose a unicast camera subnet, e.g. 192.168.10')
    return str(network.network_address).rsplit('.', 1)[0]


def discover_and_verify(subnet: str, exclude_ips=()) -> list[CameraCandidate]:
    from application.camera_discovery import discover_cameras
    from adapters.camera_identity_probe import probe_visca_identity

    prefix = validate_subnet(subnet)
    excluded = set(exclude_ips)
    candidates = (discover_cameras(prefix, exclude_ips=excluded)
                  if excluded else discover_cameras(prefix))
    # Probe only candidates inside the selected scope, never an injected/ARP
    # address outside it. Retain deterministic order and remove duplicates.
    addresses = sorted({ip for ip in candidates
                        if ip not in excluded
                        and ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(prefix + '.0/24')
                        and ip.rsplit('.', 1)[1] not in ('0', '255')})
    with ThreadPoolExecutor(max_workers=8) as pool:
        recognised = pool.map(lambda ip: probe_visca_identity(ip, VISCA_PORT), addresses)
        return [CameraCandidate(ip, ok) for ip, ok in zip(addresses, recognised)]
