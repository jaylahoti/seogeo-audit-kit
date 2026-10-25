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
                           "findings": [{"id": "title_long", "severity": "medium", "title": "Long titles", "detail": "", "pages": 500}]}],
            "geo": {"score": 70}, "robots": {"blocked_retrieval_bots": []}, "llms_txt": {"found": True}}
    cur = {"templates": [{"pattern": "/b/{slug}", "estimated_pages": 1000, "seo_score": 88, "ai_score": 60,
                          "findings": [{"id": "jsonld_missing", "severity": "high", "title": "No JSON-LD", "detail": "", "pages": 1000}]}],
           "geo": {"score": 58}, "robots": {"blocked_retrieval_bots": ["PerplexityBot"]}, "llms_txt": {"found": False}}
    kinds = {(c["kind"], c["severity"]) for c in compare(cur, prev)}
    titles = " | ".join(c["title"] for c in compare(cur, prev))
    assert ("regression", "high") in kinds  # AI readiness 80 → 60
    assert "New on /b/{slug}: No JSON-LD" in titles and "Fixed on /b/{slug}: Long titles" in titles
    assert "robots.txt now blocks PerplexityBot" in titles and "llms.txt disappeared" in titles
    assert "GEO score dropped 70 → 58" in titles
    assert "SEO dropped" not in titles  # 2 points is below the threshold


def test_monitor_routes():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    m = c.post("/monitors", json={"url": "example.com", "every_hours": 24}).json()
    assert m["url"] == "https://example.com" and m["every_hours"] == 24
    assert any(x["id"] == m["id"] for x in c.get("/monitors").json())
    assert c.delete(f"/monitors/{m['id']}").status_code == 204
    assert c.post("/monitors", json={"url": "example.com", "every_hours": 0.1}).status_code == 422
