"""Read access logs: nginx/Apache combined format, or JSON lines (Vercel log drains, Cloudflare Logpush, generic).

Only what the analysis needs is kept per line (time, IP, path, status, user agent). Raw logs are never stored.
"""

from __future__ import annotations

import gzip
import json
import re
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # compressed or plain, as sent
MAX_TEXT_BYTES = 400 * 1024 * 1024  # after decompression
MAX_LINES = 3_000_000

COMBINED = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<method>[A-Z]+) (?P<path>\S+)[^"]*" (?P<status>\d{3}) \S+'
    r'(?: "[^"]*" "(?P<ua>[^"]*)")?'
)


@dataclass
class Hit:
    ts: float | None
    ip: str
    path: str
    status: int
    ua: str


class LogTooLarge(ValueError):
    pass


def decode(body: bytes) -> str:
    if len(body) > MAX_UPLOAD_BYTES:
        raise LogTooLarge(f"Log is larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB")
    if body[:2] == b"\x1f\x8b":
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            raw = d.decompress(body, MAX_TEXT_BYTES)
        except (zlib.error, gzip.BadGzipFile) as e:
            raise ValueError("Couldn't read the gzip file") from e
        if d.unconsumed_tail:
            raise LogTooLarge(f"Log is larger than {MAX_TEXT_BYTES // 1024 // 1024} MB uncompressed")
        body = raw
    return body.decode("utf-8", errors="replace")


def _time(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        while x > 1e11:  # ns / µs / ms → s
            x /= 1000
        return x
    s = str(v)
    for fmt in ("%d/%b/%Y:%H:%M:%S %z",):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def _get(d: dict, *keys: str):
    for k in keys:
        cur = d
        for part in k.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
            if cur is None:
                break
        if cur is not None:
            return cur[0] if isinstance(cur, list) and cur else cur
    return None


def _from_json(d: dict) -> Hit | None:
    path = _get(d, "proxy.path", "path", "request_path", "ClientRequestPath", "request.path", "request.uri", "uri")
    if path is None:
        url = _get(d, "url", "request.url", "ClientRequestURI")
        path = urlsplit(str(url)).path if url else None
    ua = _get(d, "proxy.userAgent", "userAgent", "user_agent", "ClientRequestUserAgent", "http_user_agent", "request.headers.user-agent", "ua")
    status = _get(d, "proxy.statusCode", "statusCode", "status", "EdgeResponseStatus", "response.status", "status_code")
    if path is None or ua is None or status is None:
        return None
    try:
        code = int(status)
    except (TypeError, ValueError):
        return None
    ip = _get(d, "proxy.clientIp", "clientIp", "ClientIP", "ip", "remote_addr", "client_ip") or ""
    ts = _time(_get(d, "timestamp", "time", "EdgeStartTimestamp", "@timestamp", "date"))
    return Hit(ts, str(ip), str(path).split("?")[0] or "/", code, str(ua))


def parse(text: str) -> Iterator[Hit | None]:
    """Yields a Hit per line, or None for a line it couldn't read."""
    for n, line in enumerate(text.splitlines()):
        if n >= MAX_LINES:
            break
        line = line.strip()
        if not line:
            continue
        if line[0] == "{":
            try:
                d = json.loads(line)
            except ValueError:
                yield None
                continue
            yield _from_json(d) if isinstance(d, dict) else None
            continue
        m = COMBINED.match(line)
        if not m:
            yield None
            continue
        path = m["path"]
        if "://" in path:
            path = urlsplit(path).path
        yield Hit(_time(m["time"]), m["ip"], path.split("?")[0] or "/", int(m["status"]), m["ua"] or "")
