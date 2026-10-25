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
