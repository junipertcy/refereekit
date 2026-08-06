import json
from pathlib import Path
from refereekit.openreview import form as orform

FIXTURES = Path("tests/fixtures")


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def _default():
    return orform.parse_form(_load("openreview_default_form.json"))


def _iclr():
    return orform.parse_form(_load("openreview_iclr_form.json"))


def test_default_form_field_names_in_order():
    f = _default()
    assert [x.name for x in f.fields] == ["title", "review", "rating", "confidence"]
    assert f.invitation_id.endswith("Submission42/-/Official_Review")


def test_prose_and_choice_split_on_the_default_form():
    """The split is the whole 'drafted prose, blank ratings' decision."""
    f = _default()
    assert [x.name for x in f.prose_fields()] == ["title", "review"]
    assert [x.name for x in f.choice_fields()] == ["rating", "confidence"]


def test_enum_of_objects_keeps_value_and_description():
    rating = next(x for x in _default().fields if x.name == "rating")
    assert rating.enum[0] == (10, "10: Top 5% of accepted papers, seminal paper")
    assert rating.type == "integer"
    assert rating.widget == "select"


def test_enum_of_bare_scalars_gets_empty_descriptions():
    """Real venues use both enum shapes. A bare list has no descriptions."""
    ethics = next(x for x in _iclr().fields if x.name == "flag_for_ethics_review")
    assert ethics.enum == [("No ethics review needed.", ""),
                           ("Yes, Privacy and security", "")]


def test_literal_constant_field_is_skipped():
    """venueid has a literal value and no param: it is not something a
    reviewer fills in, so it is not a form field."""
    assert "venueid" not in [x.name for x in _iclr().fields]


def test_unknown_param_key_does_not_raise():
    """A venue adding a key must not break the fetch."""
    pres = next(x for x in _iclr().fields if x.name == "presentation")
    assert pres.widget == "radio"


def test_absent_order_sorts_last_and_absent_description_is_empty():
    f = _iclr()
    assert f.fields[-1].name == "code_of_conduct"
    assert f.fields[-1].description == ""


def test_optional_param_makes_the_field_not_required():
    f = _iclr()
    assert next(x for x in f.fields if x.name == "confidential_comment").required is False
    assert next(x for x in f.fields if x.name == "summary").required is True


def test_iclr_prose_fields_are_the_narrative_ones():
    assert [x.name for x in _iclr().prose_fields()] == [
        "summary", "strengths", "weaknesses", "confidential_comment"]


def test_iclr_choice_fields_include_every_rating():
    names = [x.name for x in _iclr().choice_fields()]
    for expected in ("soundness", "presentation", "contribution", "rating",
                     "confidence", "flag_for_ethics_review", "code_of_conduct"):
        assert expected in names


def test_an_enumless_array_field_is_not_prose():
    """prose_fields tested type.startswith('string'), so a string[] with no
    enum was classified as prose and would have been drafted as flowing prose
    into a field expecting a list. other_fields surfaces it instead."""
    f = orform.parse_form({"id": "x", "edit": {"note": {"content": {
        "keywords": {"value": {"param": {"type": "string[]"}}, "order": 1}}}}})
    assert [x.name for x in f.prose_fields()] == []
    assert [x.name for x in f.other_fields()] == ["keywords"]


def test_file_field_is_neither_prose_nor_choice():
    """An enum-less non-string is nothing we can draft, so it is reported to
    the referee rather than silently dropped."""
    f = _iclr()
    assert "supplementary" not in [x.name for x in f.prose_fields()]
    assert "supplementary" not in [x.name for x in f.choice_fields()]
    assert "supplementary" in [x.name for x in f.other_fields()]


def test_every_field_lands_in_exactly_one_bucket():
    f = _iclr()
    buckets = f.prose_fields() + f.choice_fields() + f.other_fields()
    assert sorted(x.name for x in buckets) == sorted(x.name for x in f.fields)


def test_missing_content_yields_an_empty_form():
    f = orform.parse_form({"id": "x", "edit": {}})
    assert f.fields == [] and f.invitation_id == "x"


def test_json_round_trip_preserves_the_split():
    before = _iclr()
    after = orform.from_json(orform.to_json(before))
    assert [x.name for x in after.prose_fields()] == [x.name for x in before.prose_fields()]
    assert after.fields[2] == before.fields[2]
