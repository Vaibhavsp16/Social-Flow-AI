"""
Outbound URL validation for website ingestion.

The crawler fetches URLs supplied by users, which is a server-side request forgery surface: without
checks a visitor could make the backend read cloud metadata (169.254.169.254), localhost admin
panels or any internal host. We allow only http(s) and only public, globally routable addresses,
and re-check after every redirect.
"""

import ipaddress
import socket
from typing import Iterable
from urllib.parse import urlparse

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = {"http", "https"}

# Hostnames that resolve to the loopback interface without needing DNS.
BLOCKED_HOSTNAMES = {
    "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback",
    "metadata.google.internal",
}


class UnsafeURLError(ValueError):
    """Raised when a URL is not safe to fetch server-side."""


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return any((
        ip.is_private,          # RFC1918, ULA
        ip.is_loopback,
        ip.is_link_local,       # 169.254.0.0/16, fe80::/10
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ))


def _resolved_addresses(hostname: str) -> Iterable[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host '{hostname}'.") from exc
    for info in infos:
        yield ipaddress.ip_address(info[4][0])


def assert_safe_url(url: str) -> str:
    """
    Validate a user-supplied URL for outbound fetching.

    Returns the URL unchanged on success; raises UnsafeURLError otherwise. Called before the
    request and again for every redirect target.
    """
    if not url or len(url) > MAX_URL_LENGTH:
        raise UnsafeURLError("URL is empty or too long.")

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http and https URLs can be ingested.")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URLs with embedded credentials are not allowed.")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise UnsafeURLError("URL has no hostname.")
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".localhost"):
        raise UnsafeURLError("Internal hostnames cannot be ingested.")

    # A literal IP is checked directly; a hostname is checked by every address it resolves to.
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        if _is_blocked_ip(literal):
            raise UnsafeURLError("Private or internal IP addresses cannot be ingested.")
        return url

    for address in _resolved_addresses(hostname):
        if _is_blocked_ip(address):
            raise UnsafeURLError(
                "This hostname resolves to a private or internal address and cannot be ingested."
            )
    return url
