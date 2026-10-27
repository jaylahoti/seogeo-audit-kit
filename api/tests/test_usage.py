import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import usage
from app.store import store


def req(ip: str, fwd: str | None = None, fly: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", fwd.encode())] if fwd else []
    if fly:
        headers.append((b"fly-client-ip", fly.encode()))
    return Request({"type": "http", "client": (ip, 1234), "headers": headers})


def test_local_requests_are_never_limited(monkeypatch):
    monkeypatch.setattr(usage.settings, "free_audits_per_day", 1)
    for _ in range(3):
        assert usage.check_visitor(req("127.0.0.1")) is None


def test_visitor_limit_and_proxy_header(monkeypatch):
    monkeypatch.setattr(usage.settings, "free_audits_per_day", 2)
    monkeypatch.setattr(usage.settings, "trust_proxy", True)
    r = req("10.0.0.5", fwd="198.51.100.200, 203.0.113.77")  # left entry is client-supplied, right one is the proxy's
    vid = usage.check_visitor(r)
    assert vid == usage.visitor_id("203.0.113.77") and "203.0.113.77" not in vid  # only a hash is kept
    store.create("https://a.test", visitor=vid)
    store.create("https://b.test", visitor=vid)
    with pytest.raises(HTTPException) as e:
        usage.check_visitor(r)
    assert e.value.status_code == 429 and "self-host" in e.value.detail
    assert usage.check_visitor(req("10.0.0.5", fwd="198.51.100.9")) is not None  # someone else is fine
    # Faking X-Forwarded-For doesn't reset the limit: Fly's own header wins.
    with pytest.raises(HTTPException):
        usage.check_visitor(req("10.0.0.5", fwd="192.0.2.1", fly="203.0.113.77"))


def test_daily_budget_counts_running_audits_at_worst_case(monkeypatch):
    monkeypatch.setattr(usage.settings, "max_audit_cost_usd", 0.5)
    spent = store.claude_spend_since(0, reserve_per_running=0.5)
    monkeypatch.setattr(usage.settings, "daily_budget_usd", spent + 1.2)
    assert usage.claude_allowed()
    rec = store.create("https://c.test")  # running: reserves $0.50
    assert usage.claude_allowed()  # spent + 0.5 reserved + 0.5 next <= cap + 0.2
    store.create("https://d.test")
    assert not usage.claude_allowed()
    rec.status, rec.result = "done", {"claude": {"spent": 0.1}}
    store.save(rec)  # finished: now counts its real cost
    assert usage.claude_allowed()
