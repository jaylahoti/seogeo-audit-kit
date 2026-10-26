import asyncio
import gzip
import json

import pytest

from app.logs.analyze import analyze
from app.logs.bots import identify
from app.logs.parse import LogTooLarge, decode, parse
from app.logs.sample import synthetic_log

TEMPLATES = [
    {"pattern": "/building/{slug}", "estimated_pages": 1000, "examples": ["https://ex.com/building/the-dakota"]},
    {"pattern": "/city/{slug}", "estimated_pages": 50, "examples": []},
]

COMBINED = (
    '203.0.113.5 - - [20/Oct/2026:10:00:00 +0000] "GET /building/the-dakota?x=1 HTTP/1.1" 200 512 "-" '
    '"Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)"\n'
    '203.0.113.6 - - [20/Oct/2026:11:00:00 +0000] "GET /city/brooklyn HTTP/1.1" 429 0 "-" "ClaudeBot/1.0"\n'
    '203.0.113.7 - - [20/Oct/2026:12:00:00 +0000] "GET /llms.txt HTTP/1.1" 200 10 "-" "PerplexityBot/1.0"\n'
    '203.0.113.8 - - [20/Oct/2026:12:30:00 +0000] "GET /app.js HTTP/1.1" 200 10 "-" "GPTBot/1.2"\n'
    '198.51.100.1 - - [20/Oct/2026:13:00:00 +0000] "GET /building/x HTTP/1.1" 200 10 "-" "Mozilla/5.0 Chrome/130"\n'
    "garbage line\n"
)


def test_identify_bots():
    assert identify("Mozilla/5.0 (compatible; ChatGPT-User/1.0)").kind == "ai_user"
    assert identify("Mozilla/5.0 (compatible; GPTBot/1.2)").name == "GPTBot"
    assert identify("Mozilla/5.0 Chrome/130") is None


def test_parse_combined_and_json():
    hits = list(parse(COMBINED))
    assert hits[0].path == "/building/the-dakota" and hits[0].status == 200 and hits[0].ts
    assert hits[-1] is None
    vercel = json.dumps({"timestamp": 1792924353126, "proxy": {"path": "/city/queens", "userAgent": ["ClaudeBot/1.0"], "statusCode": 200, "clientIp": "192.0.2.1"}})
    cf = json.dumps({"ClientRequestPath": "/building/a", "ClientRequestUserAgent": "OAI-SearchBot/1.0", "EdgeResponseStatus": 404, "EdgeStartTimestamp": 1792924353000000000})
    v, c = list(parse(vercel + "\n" + cf))
    assert v.path == "/city/queens" and v.ua == "ClaudeBot/1.0" and abs(v.ts - 1792924353.126) < 1
    assert c.status == 404 and abs(c.ts - 1792924353) < 1


def test_decode_gzip_and_limits():
    assert decode(gzip.compress(b"hello")) == "hello"
    with pytest.raises(LogTooLarge):
        decode(b"x" * (50 * 1024 * 1024 + 1))


def test_analyze_counts_page_types_errors_and_special_files():
    r = asyncio.run(analyze(COMBINED, TEMPLATES, verify=False))
    bots = {b["name"]: b for b in r["bots"]}
    assert bots["GPTBot"]["by_page_type"] == {"/building/{slug}": 1}  # the .js asset isn't counted
    assert bots["ClaudeBot"]["error_rate"] == 1.0
    assert r["top_errors"][0]["status"] == 429
    assert r["llms_txt_fetched_by"] == ["PerplexityBot"]
    assert r["other_requests"] == 1 and r["unread_lines"] == 1 and r["asset_requests"] == 1
    building = next(p for p in r["page_types"] if p["pattern"] == "/building/{slug}")
    assert building["ai_distinct_pages"] == 1 and building["ai_coverage"] == 0.001


def test_spoofed_search_bot_is_excluded(monkeypatch):
    async def fake_verify(pairs, **_):
        return {p: False for p in pairs}

    monkeypatch.setattr("app.logs.analyze.verify_ips", fake_verify)
    log = '192.0.2.9 - - [20/Oct/2026:10:00:00 +0000] "GET /city/a HTTP/1.1" 200 1 "-" "Googlebot/2.1"'
    r = asyncio.run(analyze(log, TEMPLATES))
    assert r["spoofed"] == 1 and r["bots"][0]["hits"] == 0


def test_synthetic_log_is_deterministic_and_readable():
    a = synthetic_log(TEMPLATES, seed="abc", lines=2000, now=1.8e9)
    assert a == synthetic_log(TEMPLATES, seed="abc", lines=2000, now=1.8e9)
    r = asyncio.run(analyze(a, TEMPLATES, verify=False, synthetic=True))
    assert r["synthetic"] and r["unread_lines"] == 0 and r["ai_hits"] > 0
    assert any(e["status"] == 429 and e["bot"] == "ClaudeBot" for e in r["top_errors"])
