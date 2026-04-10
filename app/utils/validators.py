import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

from app.utils.exceptions import InvalidUrlError


def normalize_url(url: str, max_url_length: int) -> str:
    candidate = url.strip()
    if not candidate:
        raise InvalidUrlError()
    if len(candidate) > max_url_length:
        raise InvalidUrlError(f"URL exceeds maximum length of {max_url_length}")

    parts = urlsplit(candidate)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc or not parts.hostname:
        raise InvalidUrlError()
    if parts.username or parts.password:
        raise InvalidUrlError("URLs with embedded credentials are not allowed")

    normalized = urlunsplit(
        (parts.scheme.lower(), parts.netloc, parts.path, parts.query, "")
    )
    if len(normalized) > max_url_length:
        raise InvalidUrlError(f"URL exceeds maximum length of {max_url_length}")

    return normalized


def _ensure_public_address(address: ipaddress._BaseAddress, host: str) -> None:
    if address.is_global:
        return
    raise InvalidUrlError(f"URL host {host} resolves to a non-public IP address")


async def ensure_url_target_allowed(url: str, *, allow_private_ips: bool) -> None:
    parts = urlsplit(url)
    host = parts.hostname
    if host is None:
        raise InvalidUrlError()

    normalized_host = host.rstrip(".")
    if normalized_host.lower() == "localhost":
        raise InvalidUrlError("Localhost URLs are not allowed")

    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError:
        address = None

    if address is not None:
        if not allow_private_ips:
            _ensure_public_address(address, normalized_host)
        return

    if allow_private_ips:
        return

    port = parts.port or (443 if parts.scheme == "https" else 80)
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(
            normalized_host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise InvalidUrlError("Unable to resolve URL hostname") from exc

    if not infos:
        raise InvalidUrlError("Unable to resolve URL hostname")

    resolved_addresses = {info[4][0] for info in infos}
    for resolved in resolved_addresses:
        _ensure_public_address(ipaddress.ip_address(resolved), normalized_host)
