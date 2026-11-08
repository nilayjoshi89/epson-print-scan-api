import os
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv6Network, ip_network

IpNetwork = IPv4Network | IPv6Network
ALLOW_ALL = "*"


def parse_networks(value: str) -> tuple[IpNetwork, ...]:
    entries = [entry.strip() for entry in value.split(",") if entry.strip()]
    if ALLOW_ALL in entries:
        return ()
    return tuple(ip_network(entry, strict=False) for entry in entries)


@dataclass(frozen=True)
class Settings:
    api_key: str
    scan_timeout_seconds: int = 600
    max_upload_bytes: int = 50 * 1024 * 1024
    allowed_networks: tuple[IpNetwork, ...] = ()

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        return cls(
            api_key=env["API_KEY"],
            scan_timeout_seconds=int(env.get("SCAN_TIMEOUT") or 600),
            max_upload_bytes=int(env.get("MAX_UPLOAD_MB") or 50) * 1024 * 1024,
            allowed_networks=parse_networks(env.get("ALLOWED_IPS") or ALLOW_ALL),
        )
