"""Fetch user-supplied URLs without letting them reach internal networks (SSRF).

Every hop (including each redirect) is resolved once, every resolved address is
checked, and the connection is made to that exact IP with the original Host header
and TLS SNI. That pins the request to the address we vetted, so a DNS answer that
changes between check and connect (DNS rebinding) can't slip through.
"""

from __future__ import annotations

import asyncio
import gzip
import io
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.config import settings

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443, None}


class BlockedURL(Exception):
    """The URL points somewhere we refuse to fetch."""


class FetchError(Exception):
    """The fetch failed for a network or size reason."""


@dataclass
class FetchResult:
    url: str  # final URL after redirects
    status: int
    headers: dict[str, str]
    body: bytes
    redirects: list[str]
    elapsed_ms: float

    def text(self) -> str:
        return self.body.decode(_charset(self.headers) or "utf-8", errors="replace")


def is_blocked_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or not addr.is_global
    )


def check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise BlockedURL(f"Only http and https URLs are allowed, got {parts.scheme or 'none'}")
    if not parts.hostname:
        raise BlockedURL("URL has no host")
    if parts.username or parts.password:
        raise BlockedURL("URLs with credentials aren't allowed")
    if parts.port not in ALLOWED_PORTS:
        raise BlockedURL(f"Port {parts.port} isn't allowed")


async def resolve_public(host: str) -> str:
    """Resolve host and return one address, refusing if ANY resolved address is internal."""
    try:
        ipaddress.ip_address(host)
        candidates = [host]
    except ValueError:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as e:
            raise FetchError(f"Couldn't resolve {host}") from e
        candidates = list(dict.fromkeys(info[4][0] for info in infos))
    if not candidates:
        raise FetchError(f"Couldn't resolve {host}")
    blocked = [ip for ip in candidates if is_blocked_ip(ip)]
    if blocked:
        raise BlockedURL(f"{host} resolves to a private or reserved address")
    # Prefer IPv4 for wider reachability.
    return next((ip for ip in candidates if ":" not in ip), candidates[0])


async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int | None = None,
    accept: str = "*/*",
) -> FetchResult:
    max_bytes = max_bytes or settings.max_page_bytes
    redirects: list[str] = []
    current = url
    loop = asyncio.get_running_loop()
    started = loop.time()

    for _ in range(settings.max_redirects + 1):
        check_url(current)
        parts = urlsplit(current)
        host = parts.hostname or ""
        ip = await resolve_public(host)
        ip_host = f"[{ip}]" if ":" in ip else ip
        netloc = f"{ip_host}:{parts.port}" if parts.port else ip_host
        pinned = urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
        host_header = host if not parts.port else f"{host}:{parts.port}"

        request = client.build_request(
            "GET",
            pinned,
            headers={"Host": host_header, "User-Agent": settings.user_agent, "Accept": accept},
            extensions={"sni_hostname": host},
        )
        try:
            response = await client.send(request, stream=True, follow_redirects=False)
        except httpx.HTTPError as e:
            raise FetchError(f"Request to {host} failed: {type(e).__name__}") from e

        try:
            if response.is_redirect and "location" in response.headers:
                redirects.append(current)
                current = urljoin(current, response.headers["location"])
                continue
            body = await _read_capped(response, max_bytes)
        finally:
            await response.aclose()

        headers = {k.lower(): v for k, v in response.headers.items()}
        # httpx already undoes Content-Encoding: gzip; this handles .xml.gz files served as-is.
        if body[:2] == b"\x1f\x8b":
            body = _gunzip_capped(body, max_bytes)
        return FetchResult(
            url=current,
            status=response.status_code,
            headers=headers,
            body=body,
            redirects=redirects,
            elapsed_ms=(loop.time() - started) * 1000,
        )

    raise FetchError(f"More than {settings.max_redirects} redirects")


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.fetch_timeout_s),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        trust_env=False,  # never route user URLs through a configured proxy
    )


async def _read_capped(response: httpx.Response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise FetchError(f"Response larger than {max_bytes // 1_000_000} MB")
        chunks.append(chunk)
    return b"".join(chunks)


def _gunzip_capped(body: bytes, max_bytes: int) -> bytes:
    out = gzip.GzipFile(fileobj=io.BytesIO(body)).read(max_bytes + 1)
    if len(out) > max_bytes:
        raise FetchError("Decompressed file is too large")
    return out


def _charset(headers: dict[str, str]) -> str | None:
    ctype = headers.get("content-type", "")
    for part in ctype.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            return part.split("=", 1)[1].strip("\"' ")
    return None
