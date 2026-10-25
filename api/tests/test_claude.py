from app.llm.judge import validate_jsonld
from app.llm.page_checks import Fact, PageCheck, Question, grounded


def test_validate_jsonld():
    good = '{"@context":"https://schema.org","@type":"ApartmentComplex","name":"{{name}}","address":{"@type":"PostalAddress","streetAddress":"{{street}}","addressLocality":"{{city}}"},"numberOfAccommodationUnits":{{units}}}'
    assert validate_jsonld(good) == (True, "")
    ok, why = validate_jsonld('{"@type":"ApartmentComplex","name":"{{name}}"}')
    assert not ok and "address" in why
    assert validate_jsonld('{"@type": "Place", "name": ')[0] is False
    assert validate_jsonld('{"name": "{{name}}"}') == (False, "no @type")


def test_grounding_drops_invented_quotes():
    from tests.test_checks import page

    p = page(1)  # text includes "Building 1 on Main Street has 120 units and a 4.1 rating from 11 renters."
    base = {'page_type': "building", 'facts': [Fact(name="units", value="120", in_text=True, in_structured_data=False)],
                'facts_up_front': True, 'title_matches_intent': True, 'better_title_template': None,
                'questions': [Question(question="How many units?", answered="yes")]}
    real = PageCheck(verdict_sentence="Building 1 on Main Street has 120 units and a 4.1 rating from 11 renters.", **base)
    fake = PageCheck(verdict_sentence="Building 1 is the best-rated building in the city with a pool.", **base)
    assert grounded(real, p).verdict_sentence is not None
    assert grounded(fake, p).verdict_sentence is None


def test_store_saves_and_reloads(tmp_path):
    from app.store import Store

    url = f"sqlite:///{tmp_path}/a.db"
    s1 = Store(url)
    rec = s1.create("https://www.example.com/")
    rec.status, rec.result = "done", {"scores": {"seo": 90, "ai": 70}, "geo": {"score": 65}}
    s1.save(rec)
    s2 = Store(url)  # a fresh process: nothing in memory
    again = s2.get(rec.id)
    assert again and again.status == "done" and again.result["geo"]["score"] == 65
    assert [h["id"] for h in s2.history("example.com")] == [rec.id]


def test_store_marks_interrupted_audits(tmp_path):
    from app.store import Store

    url = f"sqlite:///{tmp_path}/b.db"
    rec = Store(url).create("https://example.com/")  # left "queued"
    assert Store(url).get(rec.id).status == "error"


def test_monitoring_compare():
    from app.monitoring import compare

    prev = {"templates": [{"pattern": "/b/{slug}", "estimated_pages": 1000, "seo_score": 90, "ai_score": 80,
                           "findings": [{"id": "title_long", "area": "seo", "severity": "medium", "title": "Long titles", "detail": "", "pages": 500, "affected": 5, "sampled": 5, "method": "rule"}]}],
            "geo": {"score": 70}, "visibility": {"confidence": 1.0}, "robots": {"blocked_retrieval_bots": []}, "llms_txt": {"found": True}}
    cur = {"templates": [{"pattern": "/b/{slug}", "estimated_pages": 1000, "seo_score": 88, "ai_score": 60,
                          "findings": [{"id": "jsonld_missing", "area": "ai", "severity": "high", "title": "No JSON-LD", "detail": "", "pages": 1000, "affected": 5, "sampled": 5, "method": "rule"},
                                       {"id": "no_verdict", "area": "ai", "severity": "medium", "title": "No verdict", "detail": "", "pages": 1000, "affected": 5, "sampled": 5, "method": "claude"}]}],
           "geo": {"score": 58}, "visibility": {"confidence": 1.0}, "robots": {"blocked_retrieval_bots": ["PerplexityBot"]}, "llms_txt": {"found": False}}
    kinds = {(c["kind"], c["severity"]) for c in compare(cur, prev)}
    titles = " | ".join(c["title"] for c in compare(cur, prev))
    assert ("regression", "high") in kinds  # AI readiness 80 → 60
    assert "New on /b/{slug}: No JSON-LD" in titles and "Fixed on /b/{slug}: Long titles" in titles
    assert "robots.txt now blocks PerplexityBot" in titles and "llms.txt disappeared" in titles
    assert "GEO score dropped 70 → 58" in titles
    assert "SEO dropped" not in titles  # SEO got better (a long-title finding was fixed)
    assert "No verdict" not in titles  # Claude judgements don't count as regressions
    thin = {**cur, "visibility": {"confidence": 0.5}}
    assert not any("GEO" in c["title"] for c in compare(thin, prev))  # too few answers to compare


def test_monitor_routes():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    m = c.post("/monitors", json={"url": "example.com", "every_hours": 24}).json()
    assert m["url"] == "https://example.com" and m["every_hours"] == 24
    assert any(x["id"] == m["id"] for x in c.get("/monitors").json())
    assert c.delete(f"/monitors/{m['id']}").status_code == 204
    assert c.post("/monitors", json={"url": "example.com", "every_hours": 0.1}).status_code == 422


def test_cli_rules():
    import pytest

    from app.cli import evaluate, parse_rules, summary_markdown

    result = {"geo": {"score": 55}, "scores": {"seo": 90, "ai": 70}, "visibility": {"score": None},
              "templates": [{"pattern": "/b/{slug}", "findings": [{"id": "jsonld_missing", "severity": "high"}]},
                            {"pattern": "/c/{slug}", "findings": []}]}
    rules = parse_rules("geo<60, seo<80, high-issues>0, missing-jsonld, visibility<50")
    failed = evaluate(result, rules)
    assert failed == ["geo<60 (was 55)", "high-issues>0 (was 1)", "missing-jsonld (/b/{slug})"]
    with pytest.raises(SystemExit):
        parse_rules("geo>60")
    assert "**GEO 55**" in summary_markdown(result, failed, "example.com")


async def test_mcp_tools_registered():
    from app.mcp_server import server

    names = {t.name for t in await server.list_tools()}
    assert names == {"audit_site", "get_report", "get_page_type", "check_page", "get_llms_txt"}
    missing = await server.call_tool("get_report", {"audit_id": "nope"})
    assert "not found" in str(missing).lower()


def test_geo_weighs_thin_visibility_less():
    from app.checks.geo import geo_score

    full = geo_score({"score": 100}, {"score": 50}, {"score": 100, "confidence": 1.0})["score"]
    thin = geo_score({"score": 100}, {"score": 50}, {"score": 100, "confidence": 0.25})["score"]
    none = geo_score({"score": 100}, {"score": 50}, {"score": None})["score"]
    assert full == 80 and none == round((100 * 0.3 + 50 * 0.4) / 0.7)
    assert none < thin < full  # a few answers move the score, but not as much as a full sample
