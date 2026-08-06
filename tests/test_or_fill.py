import json
from pathlib import Path

import pytest

from refereekit.ingest import ingest
from refereekit.llm import FakeBackend
from refereekit.openreview import fill as orfill
from refereekit.openreview import form as orform
from refereekit.session import Session
from refereekit.types import Claim

STYLE = "style/STYLE.md"


def _form(name="openreview_iclr_form.json"):
    return orform.parse_form(
        json.loads((Path("tests/fixtures") / name).read_text()))


def _session(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(real_pdf_path))
    s.record_claim(Claim("", "page", "3"))
    s.set_state("verdict", {"recommend": "minor"})
    return s


def test_every_prose_field_gets_drafted(tmp_path, real_pdf_path):
    s = _session(tmp_path, real_pdf_path)
    got = orfill.fill(s, _form(), backend=FakeBackend("prose here"),
                      style_path=STYLE)
    assert sorted(got.values) == ["confidential_comment", "strengths",
                                  "summary", "weaknesses"]
    assert got.values["summary"] == "prose here"


def test_no_choice_field_is_ever_filled(tmp_path, real_pdf_path):
    """The load-bearing assertion. Verification is substring matching: it
    cannot justify a soundness of 3 over a 4. If drafting ever starts filling
    ratings, this fails loudly."""
    s = _session(tmp_path, real_pdf_path)
    form = _form()
    got = orfill.fill(s, form, backend=FakeBackend("prose"), style_path=STYLE)
    for f in form.choice_fields():
        assert f.name not in got.values
    payload = json.loads(orfill.to_json(got))
    for name in ("soundness", "presentation", "contribution", "rating",
                 "confidence"):
        assert payload[name] == ""


def test_blanks_list_every_field_the_referee_must_fill(tmp_path, real_pdf_path):
    s = _session(tmp_path, real_pdf_path)
    got = orfill.fill(s, _form(), backend=FakeBackend("prose"), style_path=STYLE)
    names = {f.name for f in got.blanks}
    assert {"soundness", "rating", "confidence", "supplementary"} <= names
    assert "summary" not in names


def test_the_venue_description_reaches_the_prompt(tmp_path, real_pdf_path):
    """A field's instruction is the venue telling the reviewer what belongs
    there: better guidance than anything we could invent."""
    s = _session(tmp_path, real_pdf_path)
    seen = []
    backend = FakeBackend(lambda p: seen.append(p) or "prose")
    orfill.fill(s, _form(), backend=backend, style_path=STYLE)
    joined = "\n".join(seen)
    assert "Summarize the paper in your own words." in joined
    assert "List the weaknesses of the submission." in joined
    assert "Write the 'summary' field" in joined


def test_one_backend_call_per_prose_field(tmp_path, real_pdf_path):
    """Per-field calls mean a field that fails does not lose the others."""
    s = _session(tmp_path, real_pdf_path)
    calls = []
    backend = FakeBackend(lambda p: calls.append(p) or "prose")
    orfill.fill(s, _form(), backend=backend, style_path=STYLE)
    assert len(calls) == 4


def test_length_applies_only_to_its_own_field(tmp_path, real_pdf_path):
    """Passing the whole --length map to every call would tell each one about
    lengths for sections it is not writing."""
    s = _session(tmp_path, real_pdf_path)
    seen = {}
    def canned(prompt):
        which = next(n for n in ("summary", "strengths", "weaknesses",
                                 "confidential_comment")
                     if f"'{n}' field" in prompt)
        seen[which] = prompt
        return "prose"
    orfill.fill(s, _form(), backend=FakeBackend(canned), style_path=STYLE,
                lengths={"summary": "short"})
    assert "summary=short" in seen["summary"]
    assert "summary=short" not in seen["weaknesses"]


def _fetched_only(tmp_path, real_pdf_path):
    """A session as or-fetch leaves it: paper and form, no claims, no verdict.

    or-fetch records venue, number, forum and invitation_id. Claims and the
    verdict are recorded by the review loop, so this is what or-draft sees
    when the review pass has not been run.
    """
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(real_pdf_path))
    return s


def test_a_session_with_no_claims_refuses_to_draft(tmp_path, real_pdf_path):
    """Drafting from an empty pool sends the model no verified quotation and no
    verdict, so every field comes back confabulated while the command reports
    success. An empty pool is an input error, not a citation problem."""
    s = _fetched_only(tmp_path, real_pdf_path)
    with pytest.raises(ValueError, match="no verified claims"):
        orfill.fill(s, _form(), backend=FakeBackend("prose"), style_path=STYLE)


def test_the_refusal_names_the_command_that_fills_the_pool(tmp_path,
                                                           real_pdf_path):
    """The referee needs the next command, not a diagnosis."""
    s = _fetched_only(tmp_path, real_pdf_path)
    with pytest.raises(ValueError) as ei:
        orfill.fill(s, _form(), backend=FakeBackend("prose"), style_path=STYLE)
    assert f"refereekit review {s.dir}/paper.pdf" in str(ei.value)
    assert f"--session {s.dir}" in str(ei.value)


def test_an_empty_pool_is_refused_before_any_backend_call(tmp_path,
                                                          real_pdf_path):
    """Raised before the first model call, so the failure costs nothing."""
    s = _fetched_only(tmp_path, real_pdf_path)
    calls = []
    with pytest.raises(ValueError):
        orfill.fill(s, _form(), style_path=STYLE,
                    backend=FakeBackend(lambda p: calls.append(p) or "prose"))
    assert calls == []


def test_a_verdict_with_no_claims_still_drafts(tmp_path, real_pdf_path):
    """A verdict on its own is a real pool: the referee reached a
    recommendation without needing to quote the manuscript."""
    s = _fetched_only(tmp_path, real_pdf_path)
    s.set_state("verdict", {"recommend": "minor"})
    got = orfill.fill(s, _form(), backend=FakeBackend("prose"),
                      style_path=STYLE)
    assert got.values["summary"] == "prose"


def test_unknown_length_name_is_an_error(tmp_path, real_pdf_path):
    """A typo, or a form that differs from the one the referee expected. Both
    are worth hearing about rather than silently ignoring."""
    s = _session(tmp_path, real_pdf_path)
    with pytest.raises(ValueError, match="nosuchfield"):
        orfill.fill(s, _form(), backend=FakeBackend("x"), style_path=STYLE,
                    lengths={"nosuchfield": "short"})


def test_flags_are_deduplicated_across_fields(tmp_path, real_pdf_path):
    """The same unpooled anchor cited in two fields is one problem, not two."""
    s = _session(tmp_path, real_pdf_path)
    got = orfill.fill(s, _form(), backend=FakeBackend("See p. 999 for this."),
                      style_path=STYLE)
    assert len(got.flags) == 1
    assert got.flags[0].anchor == "999"


def test_markdown_shows_drafted_prose_and_the_options_to_choose_from(
        tmp_path, real_pdf_path):
    s = _session(tmp_path, real_pdf_path)
    form = _form()
    got = orfill.fill(s, form, backend=FakeBackend("drafted prose"),
                      style_path=STYLE)
    md = orfill.to_markdown(form, got)
    assert "## summary" in md and "drafted prose" in md
    assert "## rating" in md
    assert "8: accept, good paper" in md
    assert "fill in yourself" in md


def test_markdown_keeps_the_venue_field_order(tmp_path, real_pdf_path):
    s = _session(tmp_path, real_pdf_path)
    form = _form()
    md = orfill.to_markdown(form, orfill.fill(
        s, form, backend=FakeBackend("p"), style_path=STYLE))
    assert md.index("## summary") < md.index("## weaknesses") < md.index("## rating")


def test_default_form_works_too(tmp_path, real_pdf_path):
    """No venue-specific code: the plain default form goes through unchanged."""
    s = _session(tmp_path, real_pdf_path)
    form = _form("openreview_default_form.json")
    got = orfill.fill(s, form, backend=FakeBackend("prose"), style_path=STYLE)
    assert sorted(got.values) == ["review", "title"]
    assert {f.name for f in got.blanks} == {"rating", "confidence"}
