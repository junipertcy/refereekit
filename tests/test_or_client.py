import json
from pathlib import Path

import pytest

from refereekit.openreview import client as orclient
from refereekit.session import Session
from tests.openreview_fakes import (FakeEdge, FakeGroup, FakeNote, FakeORClient)

VENUE = "Test.cc/2027/Conference"


def _sub(number=42, nid="note-42", title="A Paper About Things", pdf=True):
    content = {"title": {"value": title}}
    if pdf:
        content["pdf"] = {"value": "/pdf/aaa.pdf"}
    return FakeNote(id=nid, number=number, content=content)


def _client(**kw):
    notes = kw.pop("notes", {42: _sub()})
    return FakeORClient(notes=notes, **kw)


# ---- assignments

def test_list_assignments_returns_number_and_title():
    c = _client(edges=[FakeEdge(head="note-42")])
    got = orclient.list_assignments(c, VENUE)
    assert [(a.number, a.title, a.forum) for a in got] == [
        (42, "A Paper About Things", "note-42")]


def test_list_assignments_queries_the_assignment_invitation_with_our_profile():
    c = _client(edges=[FakeEdge(head="note-42")])
    orclient.list_assignments(c, VENUE)
    kw = c.kwargs_for("get_all_edges")[0]
    assert kw["invitation"] == f"{VENUE}/Reviewers/-/Assignment"
    assert kw["tail"] == "~Test_User1"
    assert "limit" not in kw and "offset" not in kw   # v2 streams


def test_list_assignments_sorts_by_paper_number():
    notes = {7: _sub(7, "note-7", "Seven"), 42: _sub(42, "note-42", "Fortytwo")}
    c = _client(notes=notes,
                edges=[FakeEdge(head="note-42"), FakeEdge(head="note-7")])
    assert [a.number for a in orclient.list_assignments(c, VENUE)] == [7, 42]


def test_no_assignments_is_an_empty_list_not_an_error():
    assert orclient.list_assignments(_client(edges=[]), VENUE) == []


def test_edge_failure_becomes_an_ORError_naming_the_venue():
    c = _client(raise_on={"get_all_edges"})
    with pytest.raises(orclient.ORError, match="check the venue id"):
        orclient.list_assignments(c, VENUE)


# ---- submission

def test_fetch_submission_returns_pdf_bytes_and_forum_id():
    c = _client()
    pdf, forum = orclient.fetch_submission(c, VENUE, 42)
    assert pdf == b"%PDF-1.4 fake"
    assert forum == "note-42"


def test_fetch_submission_passes_field_name_by_keyword():
    """v2 is get_attachment(field_name, id=...), the reverse of the v1 example
    that circulates widely. Positional args send the note id as the field name
    and 404. This test is the guard against that regression."""
    c = _client()
    orclient.fetch_submission(c, VENUE, 42)
    kw = c.kwargs_for("get_attachment")[0]
    assert kw["field_name"] == "pdf"
    assert kw["id"] == "note-42"


def test_fetch_submission_queries_by_number_not_by_fetching_everything():
    c = _client()
    orclient.fetch_submission(c, VENUE, 42)
    kw = c.kwargs_for("get_all_notes")[0]
    assert kw["number"] == 42
    assert kw["invitation"] == f"{VENUE}/-/Submission"


def test_unassigned_submission_says_so():
    c = _client(notes={})
    with pytest.raises(orclient.ORError, match="not assigned to you"):
        orclient.fetch_submission(c, VENUE, 42)


def test_submission_without_a_pdf_says_so():
    c = _client(notes={42: _sub(pdf=False)})
    with pytest.raises(orclient.ORError, match="no pdf attachment"):
        orclient.fetch_submission(c, VENUE, 42)


# ---- form

def test_fetch_form_parses_the_invitation():
    inv = json.loads(Path("tests/fixtures/openreview_default_form.json").read_text())
    c = _client(invitation=inv)
    form = orclient.fetch_form(c, VENUE, 42)
    assert [f.name for f in form.prose_fields()] == ["title", "review"]
    assert c.kwargs_for("get_invitation")[0]["id"] == \
        f"{VENUE}/Submission42/-/Official_Review"


def test_fetch_form_is_none_before_the_review_stage_opens():
    """No invitation yet is normal, not an error: the referee still wants the
    pdf, which is the part they need first."""
    assert orclient.fetch_form(_client(invitation=None), VENUE, 42) is None


# ---- our own anonymous groups

def test_our_group_ids_queries_by_prefix_and_signatory():
    c = _client(groups=[FakeGroup(id=f"{VENUE}/Submission42/Reviewer_abc1")])
    got = orclient.our_group_ids(c, VENUE, 42)
    assert got == {f"{VENUE}/Submission42/Reviewer_abc1"}
    kw = c.kwargs_for("get_groups")[0]
    assert kw["prefix"] == f"{VENUE}/Submission42/Reviewer_"
    assert kw["signatory"] == "~Test_User1"


def test_our_group_ids_is_none_when_the_lookup_fails():
    """None is not an empty set. Both leave ownership unverifiable, but only
    one of them is a fault the referee can act on."""
    c = _client(raise_on={"get_groups"})
    assert orclient.our_group_ids(c, VENUE, 42) is None


def test_our_group_ids_is_an_empty_set_when_no_group_matches():
    """A successful lookup that finds nothing. A venue naming its groups
    Reviewers or AnonReviewer1 rather than Reviewer_ lands here."""
    assert orclient.our_group_ids(_client(groups=[]), VENUE, 42) == set()


# ---- replies

def _reply(nid, tcdate, sigs, invitation, body="Thanks for the review."):
    return {"id": nid, "tcdate": tcdate, "signatures": sigs,
            "invitations": [invitation], "content": {"comment": {"value": body}}}


def test_fetch_replies_flattens_the_details_replies():
    r = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    assert orclient.fetch_replies(_client(replies=[r]), "note-42") == [r]


def test_store_replies_names_files_by_note_id_and_tcdate(tmp_path):
    s = Session.create(tmp_path, "p")
    r = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    written, skipped, held = orclient.store_replies(s, [r], set())
    assert written == ["r1-1700000000000.txt"] and skipped == []
    assert held == []
    assert (s.theirs_dir / "r1-1700000000000.txt").exists()


def test_an_official_review_is_held_back_when_ownership_is_unverified(tmp_path):
    """With no skip set, an Official_Review signed by a reviewer group could be
    ours. theirs/ means received from others, and or-responses feeds everything
    in it to the model as an author response, so our own review landing there
    would be analyzed as agreeing with itself."""
    s = Session.create(tmp_path, "p")
    r = _reply("r-unknown", 1700000000000,
               [f"{VENUE}/Submission42/Reviewer_abc1"], "X/-/Official_Review")
    written, skipped, held = orclient.store_replies(s, [r], set())
    assert written == [] and skipped == []
    assert held == ["r-unknown-1700000000000.txt"]
    assert not (s.theirs_dir / "r-unknown-1700000000000.txt").exists()


def test_a_profile_signed_note_is_stored_even_with_no_skip_set(tmp_path):
    """A ~-prefixed signature is a named profile, so it is not one of our own
    anonymous reviewer groups. An author comment must still arrive."""
    s = Session.create(tmp_path, "p")
    r = _reply("r-author", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    written, _, held = orclient.store_replies(s, [r], set())
    assert written == ["r-author-1700000000000.txt"] and held == []


def test_a_profile_signed_official_review_is_stored(tmp_path):
    """A venue with non-anonymous reviewing signs reviews with the profile id.
    That cannot be one of our anonymous groups, so it is received from others."""
    s = Session.create(tmp_path, "p")
    r = _reply("r-named", 1700000000000, ["~Co_Reviewer1"], "X/-/Official_Review")
    written, _, held = orclient.store_replies(s, [r], set())
    assert written == ["r-named-1700000000000.txt"] and held == []


def test_a_non_review_group_signed_note_is_stored_with_no_skip_set(tmp_path):
    """Holding back is scoped to Official_Review. An area chair's comment is
    not something we could have written, so an empty skip set does not
    quarantine the whole discussion."""
    s = Session.create(tmp_path, "p")
    r = _reply("r-ac", 1700000000000,
               [f"{VENUE}/Submission42/Area_Chairs"], "X/-/Meta_Review")
    written, _, held = orclient.store_replies(s, [r], set())
    assert written == ["r-ac-1700000000000.txt"] and held == []


def test_a_known_skip_set_stores_a_coreviewer_official_review(tmp_path):
    """The hold-back is only for an unverified skip set. Once ownership is
    known, a co-reviewer's report is received from others and belongs in
    theirs/, exactly as before."""
    s = Session.create(tmp_path, "p")
    mine = f"{VENUE}/Submission42/Reviewer_abc1"
    co = _reply("r-co", 1700000000000,
                [f"{VENUE}/Submission42/Reviewer_zzz9"], "X/-/Official_Review")
    written, _, held = orclient.store_replies(s, [co], {mine})
    assert written == ["r-co-1700000000000.txt"] and held == []


def test_stored_reply_header_says_what_it_is(tmp_path):
    s = Session.create(tmp_path, "p")
    r = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    orclient.store_replies(s, [r], set())
    text = (s.theirs_dir / "r1-1700000000000.txt").read_text()
    assert text.startswith("# openreview note r1 by ~Author_One1 at 2023-11-14")
    assert "# invitation: X/-/Rebuttal" in text
    assert "Thanks for the review." in text


def test_refetching_an_unchanged_reply_is_skipped_not_an_error(tmp_path):
    """put_theirs is write-once, so a naive re-fetch would raise
    ProvenanceError. Same note, same tcdate, same filename: skip it."""
    s = Session.create(tmp_path, "p")
    r = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    orclient.store_replies(s, [r], set())
    written, skipped, _ = orclient.store_replies(s, [r], set())
    assert written == [] and skipped == ["r1-1700000000000.txt"]


def test_a_revised_reply_becomes_a_second_file_and_both_remain(tmp_path):
    """A rebuttal edited during the discussion period has a new tcdate, so it
    is a new file. Both versions are kept and the change is visible."""
    s = Session.create(tmp_path, "p")
    first = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal", "v1")
    second = _reply("r1", 1700009999000, ["~Author_One1"], "X/-/Rebuttal", "v2")
    orclient.store_replies(s, [first], set())
    written, _, _ = orclient.store_replies(s, [second], set())
    assert written == ["r1-1700009999000.txt"]
    assert (s.theirs_dir / "r1-1700000000000.txt").read_text().endswith("v1\n")
    assert (s.theirs_dir / "r1-1700009999000.txt").read_text().endswith("v2\n")


def test_our_own_review_never_lands_in_theirs(tmp_path):
    """Storing our own review under theirs/ would recreate exactly the
    our-draft-versus-their-report confusion that ours/ and theirs/ exist to
    prevent."""
    s = Session.create(tmp_path, "p")
    mine = f"{VENUE}/Submission42/Reviewer_abc1"
    ours = _reply("r-mine", 1700000000000, [mine], "X/-/Official_Review")
    theirs = _reply("r-them", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    coreviewer = _reply("r-co", 1700000000000,
                        [f"{VENUE}/Submission42/Reviewer_zzz9"],
                        "X/-/Official_Review")
    written, _, _ = orclient.store_replies(s, [ours, theirs, coreviewer], {mine})
    assert sorted(written) == ["r-co-1700000000000.txt",
                              "r-them-1700000000000.txt"]
    assert not (s.theirs_dir / "r-mine-1700000000000.txt").exists()


def test_make_client_without_credentials_says_which_variables(monkeypatch):
    _stub_openreview(monkeypatch, lambda **kw: "client")
    monkeypatch.setenv("OPENREVIEW_USERNAME", "")
    monkeypatch.delenv("OPENREVIEW_PASSWORD", raising=False)
    with pytest.raises(orclient.ORError,
                       match="OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD"):
        orclient.make_client()


def _stub_openreview(monkeypatch, factory):
    """Stand in for the openreview package so these tests run identically with
    the extra installed and without it."""
    import sys
    import types
    mod = types.ModuleType("openreview")
    mod.api = types.SimpleNamespace(OpenReviewClient=factory)
    monkeypatch.setitem(sys.modules, "openreview", mod)


def test_make_client_error_never_echoes_the_password(monkeypatch):
    """A credential in an exception message reaches every log that catches it."""
    def explode(**kw):
        raise RuntimeError(f"401 rejected {kw['username']}:{kw['password']}")
    _stub_openreview(monkeypatch, explode)
    monkeypatch.setenv("OPENREVIEW_USERNAME", "someone@example.com")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "hunter2-do-not-print")
    with pytest.raises(orclient.ORError) as ei:
        orclient.make_client()
    assert "hunter2" not in str(ei.value)
    assert "someone@example.com" in str(ei.value)


def test_make_client_passes_the_baseurl_through(monkeypatch):
    seen = {}
    _stub_openreview(monkeypatch, lambda **kw: seen.update(kw) or "client")
    monkeypatch.setenv("OPENREVIEW_USERNAME", "u")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "p")
    assert orclient.make_client("https://devapi2.openreview.net") == "client"
    assert seen["baseurl"] == "https://devapi2.openreview.net"


def test_make_client_without_the_extra_names_the_install_command(monkeypatch):
    import sys
    # A None entry makes the import fail the same way an absent package does.
    monkeypatch.setitem(sys.modules, "openreview", None)
    monkeypatch.setenv("OPENREVIEW_USERNAME", "u")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "p")
    with pytest.raises(orclient.ORError, match=r'pip install -e "\.\[openreview\]"'):
        orclient.make_client()
