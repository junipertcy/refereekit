import json
from pathlib import Path

from refereekit.cli import main
from refereekit.ingest import ingest
from refereekit.llm import FakeBackend
from refereekit.memory import Note, SQLiteMemoryStore
from refereekit.openreview import client as orclient
from refereekit.session import Session
from refereekit.types import Claim
from tests.openreview_fakes import FakeEdge, FakeGroup, FakeNote, FakeORClient

VENUE = "Test.cc/2027/Conference"


def _fake_client(real_pdf_path, **kw):
    note = FakeNote(id="note-42", number=42,
                    content={"title": {"value": "A Paper"},
                             "pdf": {"value": "/pdf/a.pdf"}})
    inv = json.loads(
        Path("tests/fixtures/openreview_iclr_form.json").read_text())
    defaults = dict(notes={42: note}, edges=[FakeEdge(head="note-42")],
                    invitation=inv, pdf=real_pdf_path.read_bytes(),
                    groups=[FakeGroup(id=f"{VENUE}/Submission42/Reviewer_me1")])
    defaults.update(kw)
    return FakeORClient(**defaults)


def _patch(monkeypatch, client):
    monkeypatch.setattr(orclient, "make_client", lambda baseurl=None: client)


def test_or_fetch_lists_assignments(monkeypatch, tmp_path, real_pdf_path, capsys):
    _patch(monkeypatch, _fake_client(real_pdf_path))
    rc = main(["or-fetch", "--venue", VENUE, "--session", str(tmp_path / "s")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "42" in out and "A Paper" in out


def test_or_fetch_with_no_assignments_says_so(monkeypatch, tmp_path,
                                              real_pdf_path, capsys):
    _patch(monkeypatch, _fake_client(real_pdf_path, edges=[]))
    rc = main(["or-fetch", "--venue", VENUE, "--session", str(tmp_path / "s")])
    assert rc == 0
    assert "no assignments" in capsys.readouterr().out


def test_or_fetch_number_writes_pdf_doc_and_form(monkeypatch, tmp_path,
                                                 real_pdf_path, capsys):
    _patch(monkeypatch, _fake_client(real_pdf_path))
    sess = tmp_path / "s"
    rc = main(["or-fetch", "--venue", VENUE, "--number", "42",
               "--session", str(sess)])
    assert rc == 0
    assert (sess / "paper.pdf").exists()
    assert (sess / "doc.json").exists()
    form = json.loads((sess / "form.json").read_text())
    assert form["invitation_id"].endswith("Submission42/-/Official_Review")
    assert Session(sess).get_state("venue") == VENUE
    assert Session(sess).get_state("number") == 42


def test_or_fetch_stores_replies_but_not_our_own(monkeypatch, tmp_path,
                                                 real_pdf_path):
    mine = f"{VENUE}/Submission42/Reviewer_me1"
    replies = [
        {"id": "r-them", "tcdate": 1700000000000, "signatures": ["~Author_One1"],
         "invitations": [f"{VENUE}/Submission42/-/Rebuttal"],
         "content": {"comment": {"value": "We revised Sec. 3."}}},
        {"id": "r-mine", "tcdate": 1700000000000, "signatures": [mine],
         "invitations": [f"{VENUE}/Submission42/-/Official_Review"],
         "content": {"review": {"value": "my own review"}}},
    ]
    _patch(monkeypatch, _fake_client(real_pdf_path, replies=replies))
    sess = tmp_path / "s"
    assert main(["or-fetch", "--venue", VENUE, "--number", "42",
                 "--session", str(sess)]) == 0
    names = [p.name for p in (sess / "theirs").iterdir()]
    assert names == ["r-them-1700000000000.txt"]


def test_or_fetch_warns_and_holds_back_when_ownership_is_unverified(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """A group lookup that fails, or a venue whose group naming differs from
    the Reviewer_ prefix, leaves the skip set unusable. Our own Official_Review
    would then be written to theirs/ and or-responses would feed it to the
    model as an author response. It is held back, and the referee is told
    which note and why, not left to discover their own text quoted back."""
    replies = [
        {"id": "r-them", "tcdate": 1700000000000, "signatures": ["~Author_One1"],
         "invitations": [f"{VENUE}/Submission42/-/Rebuttal"],
         "content": {"comment": {"value": "We revised Sec. 3."}}},
        {"id": "r-maybe-mine", "tcdate": 1700000000000,
         "signatures": [f"{VENUE}/Submission42/AnonReviewer1"],
         "invitations": [f"{VENUE}/Submission42/-/Official_Review"],
         "content": {"review": {"value": "placeholder review prose"}}},
    ]
    _patch(monkeypatch, _fake_client(real_pdf_path, replies=replies,
                                     raise_on={"get_groups"}))
    sess = tmp_path / "s"
    assert main(["or-fetch", "--venue", VENUE, "--number", "42",
                 "--session", str(sess)]) == 0
    names = [p.name for p in (sess / "theirs").iterdir()]
    assert names == ["r-them-1700000000000.txt"]
    out = capsys.readouterr().out
    assert "1 held back" in out
    assert "r-maybe-mine" in out
    assert "could not confirm" in out


def test_or_responses_never_sees_a_held_back_review(monkeypatch, tmp_path,
                                                    real_pdf_path):
    """The consequence the hold-back exists to prevent: our own review read
    back out of theirs/ and analyzed as what the authors said."""
    replies = [
        {"id": "r-them", "tcdate": 1700000000000, "signatures": ["~Author_One1"],
         "invitations": [f"{VENUE}/Submission42/-/Rebuttal"],
         "content": {"comment": {"value": "We revised Sec. 3."}}},
        {"id": "r-maybe-mine", "tcdate": 1700000000000,
         "signatures": [f"{VENUE}/Submission42/Reviewer_xyz9"],
         "invitations": [f"{VENUE}/Submission42/-/Official_Review"],
         "content": {"review": {"value": "unmistakable placeholder marker"}}},
    ]
    _patch(monkeypatch, _fake_client(real_pdf_path, replies=replies,
                                     raise_on={"get_groups"}))
    sess = tmp_path / "s"
    main(["or-fetch", "--venue", VENUE, "--number", "42", "--session", str(sess)])
    seen = []
    monkeypatch.setattr("refereekit.cli._backend",
                        lambda: FakeBackend(lambda p: seen.append(p) or "ok"))
    assert main(["or-responses", "--session", str(sess)]) == 0
    assert "unmistakable placeholder marker" not in seen[0]


def test_or_fetch_before_the_review_stage_still_gets_the_pdf(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    _patch(monkeypatch, _fake_client(real_pdf_path, invitation=None))
    sess = tmp_path / "s"
    rc = main(["or-fetch", "--venue", VENUE, "--number", "42",
               "--session", str(sess)])
    assert rc == 0
    assert (sess / "doc.json").exists()
    assert not (sess / "form.json").exists()
    assert "no review form" in capsys.readouterr().out


def test_or_fetch_keeps_the_pdf_when_the_discussion_cannot_be_read(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """fetch_form and our_group_ids degrade rather than raise. A 500 from the
    discussion endpoint used to exit 2 with paper.pdf, doc.json, form.json and
    state.json already written, which is the half-built session the %PDF check
    exists to prevent."""
    _patch(monkeypatch, _fake_client(real_pdf_path,
                                     raise_on={"get_all_notes/forum"}))
    sess = tmp_path / "s"
    rc = main(["or-fetch", "--venue", VENUE, "--number", "42",
               "--session", str(sess)])
    assert rc == 0
    assert (sess / "doc.json").exists() and (sess / "form.json").exists()
    out = capsys.readouterr().out
    assert "could not read the discussion" in out
    assert "theirs/ left empty" in out


def test_or_fetch_says_why_there_is_no_form_when_the_lookup_failed(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """A transient failure and an unopened review stage produced the same
    message, so the referee ran or-draft and was told to run the or-fetch they
    had just run."""
    _patch(monkeypatch, _fake_client(real_pdf_path,
                                     raise_on={"get_invitation"}))
    sess = tmp_path / "s"
    assert main(["or-fetch", "--venue", VENUE, "--number", "42",
                 "--session", str(sess)]) == 0
    out = capsys.readouterr().out
    assert "no review form" in out
    assert "fake failure in get_invitation" in out


def test_or_fetch_lists_the_rest_when_one_assignment_is_unreadable(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    c = _fake_client(real_pdf_path)
    c._edges = [FakeEdge(head="note-gone"), FakeEdge(head="note-42")]
    _patch(monkeypatch, c)
    rc = main(["or-fetch", "--venue", VENUE, "--session", str(tmp_path / "s")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "A Paper" in out
    assert "note-gone" in out


def test_or_fetch_reports_an_or_error_as_exit_2(monkeypatch, tmp_path, capsys):
    def boom(baseurl=None):
        raise orclient.ORError("set OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD")
    monkeypatch.setattr(orclient, "make_client", boom)
    rc = main(["or-fetch", "--venue", VENUE, "--session", str(tmp_path / "s")])
    assert rc == 2
    assert "OPENREVIEW_USERNAME" in capsys.readouterr().err


def test_or_fetch_baseurl_reaches_the_client(monkeypatch, tmp_path, real_pdf_path):
    seen = {}
    c = _fake_client(real_pdf_path)
    monkeypatch.setattr(orclient, "make_client",
                        lambda baseurl=None: seen.setdefault("u", baseurl) or c)
    main(["or-fetch", "--venue", VENUE, "--session", str(tmp_path / "s"),
          "--baseurl", "https://devapi2.openreview.net"])
    assert seen["u"] == "https://devapi2.openreview.net"


def test_or_fetch_on_a_download_that_is_not_a_pdf_exits_2(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """A truncated or error-page download must not leave a half-built session
    passing for a fetched paper."""
    _patch(monkeypatch, _fake_client(real_pdf_path, pdf=b"<html>error</html>"))
    sess = tmp_path / "s"
    rc = main(["or-fetch", "--venue", VENUE, "--number", "42",
               "--session", str(sess)])
    assert rc == 2
    assert not (sess / "doc.json").exists()
    assert capsys.readouterr().err.startswith("error:")


def test_or_fetch_refuses_to_repoint_a_session_at_another_paper(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """Session.create is exist_ok, so fetching 42 then 43 into the same session
    overwrote paper.pdf, doc.json and form.json, left theirs/ holding both
    papers' notes, and left a stale ours/openreview.md that or-responses would
    read as our review of the wrong paper."""
    note43 = FakeNote(id="note-43", number=43,
                      content={"title": {"value": "Another Paper"},
                               "pdf": {"value": "/pdf/b.pdf"}})
    c = _fake_client(real_pdf_path)
    c._notes[43] = note43
    _patch(monkeypatch, c)
    sess = tmp_path / "s"
    assert main(["or-fetch", "--venue", VENUE, "--number", "42",
                 "--session", str(sess)]) == 0
    rc = main(["or-fetch", "--venue", VENUE, "--number", "43",
               "--session", str(sess)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "42" in err and "43" in err
    assert Session(sess).get_state("number") == 42


def test_refetching_the_same_number_into_the_same_session_still_works(
        monkeypatch, tmp_path, real_pdf_path):
    """The normal way to pick up a new rebuttal."""
    _patch(monkeypatch, _fake_client(real_pdf_path))
    sess = tmp_path / "s"
    assert main(["or-fetch", "--venue", VENUE, "--number", "42",
                 "--session", str(sess)]) == 0
    assert main(["or-fetch", "--venue", VENUE, "--number", "42",
                 "--session", str(sess)]) == 0


def test_or_fetch_and_or_draft_agree_on_how_many_fields_you_fill_in(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """Both print the same phrase about the same form in the same session, so
    they must print the same number."""
    _patch(monkeypatch, _fake_client(real_pdf_path))
    sess = tmp_path / "s"
    main(["or-fetch", "--venue", VENUE, "--number", "42", "--session", str(sess)])
    fetched = capsys.readouterr().out
    n_fetch = int(next(line for line in fetched.splitlines()
                       if "to fill in yourself" in line).split(", ")[1].split()[0])
    s = Session(sess)
    s.record_claim(Claim("", "page", "3"))
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    main(["or-draft", "--session", str(sess)])
    drafted = capsys.readouterr().out
    n_draft = sum(1 for line in drafted.splitlines()
                  if line.startswith("  ") and "FLAG" not in line)
    assert n_fetch == n_draft


def test_or_draft_passes_the_venue_and_the_memory_db_to_the_draft(
        monkeypatch, tmp_path, real_pdf_path):
    """or-fetch records the venue, review wires --db and --venue through, and
    or-draft dropped both, silently discarding the accumulated voice and
    verdict patterns the project deliberately built."""
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    db = tmp_path / "memory.db"
    store = SQLiteMemoryStore(str(db))
    store.store(Note("prefers a short summary", VENUE, "style"),
                Session(sess).load_doc())
    seen = []
    monkeypatch.setattr("refereekit.cli._backend",
                        lambda: FakeBackend(lambda p: seen.append(p) or "ok"))
    assert main(["or-draft", "--session", str(sess), "--db", str(db)]) == 0
    assert "prefers a short summary" in seen[0]


def _fetched_session(monkeypatch, tmp_path, real_pdf_path):
    _patch(monkeypatch, _fake_client(real_pdf_path))
    sess = tmp_path / "s"
    main(["or-fetch", "--venue", VENUE, "--number", "42", "--session", str(sess)])
    s = Session(sess)
    s.record_claim(Claim("", "page", "3"))
    s.set_state("verdict", {"recommend": "minor"})
    return sess


def test_or_draft_writes_markdown_and_json(monkeypatch, tmp_path,
                                           real_pdf_path, capsys):
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Drafted prose.")
    rc = main(["or-draft", "--session", str(sess)])
    assert rc == 0
    md = (sess / "ours" / "openreview.md").read_text()
    assert "## summary" in md and "Drafted prose." in md
    payload = json.loads((sess / "ours" / "openreview.json").read_text())
    assert payload["summary"] == "Drafted prose."
    assert payload["rating"] == ""
    out = capsys.readouterr().out
    assert "to fill in yourself" in out and "rating" in out


def test_or_draft_on_a_freshly_fetched_session_refuses_to_confabulate(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """or-fetch records venue, number and forum; the claim pool comes from a
    review pass. Without one, every field would be drafted from an empty pool
    and the command would report success. It must exit 2 and name the command
    that fills the pool instead."""
    _patch(monkeypatch, _fake_client(real_pdf_path))
    sess = tmp_path / "s"
    main(["or-fetch", "--venue", VENUE, "--number", "42", "--session", str(sess)])
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    rc = main(["or-draft", "--session", str(sess)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "no verified claims" in err
    assert f"refereekit review {sess}/paper.pdf --session {sess}" in err
    assert not (sess / "ours" / "openreview.md").exists()


def test_or_draft_refuses_an_empty_pool_before_building_a_backend(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """An empty pool is an input error, so it is reported before a backend is
    constructed: a missing optional extra must not mask it."""
    _patch(monkeypatch, _fake_client(real_pdf_path))
    sess = tmp_path / "s"
    main(["or-fetch", "--venue", VENUE, "--number", "42", "--session", str(sess)])
    import refereekit.cli as climod

    def no_backend():
        raise ModuleNotFoundError("No module named 'anthropic'")
    monkeypatch.setattr(climod, "_backend", no_backend)
    rc = main(["or-draft", "--session", str(sess)])
    assert rc == 2
    assert "no verified claims" in capsys.readouterr().err


def test_or_draft_without_a_form_says_to_fetch_first(tmp_path, capsys):
    s = Session.create(tmp_path, "s")
    rc = main(["or-draft", "--session", str(s.dir)])
    assert rc == 2
    assert "run or-fetch --number first" in capsys.readouterr().err


def test_or_draft_with_an_unknown_length_name_exits_2(monkeypatch, tmp_path,
                                                      real_pdf_path, capsys):
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    rc = main(["or-draft", "--session", str(sess), "--length", "nope=short"])
    assert rc == 2
    assert "nope" in capsys.readouterr().err


def test_an_unknown_length_name_is_reported_before_the_backend_is_built(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """The name=value parse was hoisted out of the fill() call, but the "does
    this field exist" check stayed inside fill(), which runs after _backend().
    With the anthropic extra absent the referee was told their install was
    broken when the real problem was a typo in the flag. Asserting on exit 2
    alone would pass under either ordering, so this asserts on the message."""
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    import refereekit.cli as climod

    def no_backend():
        raise ModuleNotFoundError("No module named 'anthropic'")
    monkeypatch.setattr(climod, "_backend", no_backend)
    rc = main(["or-draft", "--session", str(sess), "--length", "nope=short"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "--length" in err and "nope" in err
    assert "anthropic" not in err


def test_or_draft_validates_length_before_building_a_backend(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """A malformed --length is an input error, so it must be reported before a
    backend is constructed. Backend construction fails when the llm extra is
    absent, which would otherwise mask the exit 2 with a traceback."""
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    import refereekit.cli as climod

    def no_backend():
        raise ModuleNotFoundError("No module named 'anthropic'")
    monkeypatch.setattr(climod, "_backend", no_backend)
    rc = main(["or-draft", "--session", str(sess), "--length", "summary"])
    assert rc == 2
    assert "--length takes name=value" in capsys.readouterr().err


def test_or_draft_reports_a_missing_llm_extra_as_exit_2(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    import refereekit.cli as climod

    def no_backend():
        raise ModuleNotFoundError("No module named 'anthropic'")
    monkeypatch.setattr(climod, "_backend", no_backend)
    rc = main(["or-draft", "--session", str(sess)])
    assert rc == 2
    assert "anthropic" in capsys.readouterr().err


def test_or_draft_renders_a_non_numeric_enum_without_a_fake_range(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """A numeric enum has a low-high span. A textual one does not, and printing
    '(I agree-I agree)' as though it were a range misreads the form."""
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    assert main(["or-draft", "--session", str(sess)]) == 0
    out = capsys.readouterr().out
    assert "(1-4)" in out                       # soundness, numeric
    assert "(I agree-I agree)" not in out
    assert "I agree" in out                     # still shown, as an option
    for line in out.splitlines():
        if line.startswith("  code_of_conduct"):
            assert len(line) < 100


def test_or_responses_on_a_nonexistent_session_creates_nothing(tmp_path, capsys):
    sess = tmp_path / "nope"
    rc = main(["or-responses", "--session", str(sess)])
    assert rc == 2
    assert "no session at" in capsys.readouterr().err
    assert not sess.exists()


def test_or_responses_writes_the_analysis(monkeypatch, tmp_path,
                                         real_pdf_path, capsys):
    mine = f"{VENUE}/Submission42/Reviewer_me1"
    replies = [{"id": "r-them", "tcdate": 1700000000000,
                "signatures": ["~Author_One1"],
                "invitations": [f"{VENUE}/Submission42/-/Rebuttal"],
                "content": {"comment": {"value": "We revised Sec. 3."}}}]
    _patch(monkeypatch, _fake_client(real_pdf_path, replies=replies))
    sess = tmp_path / "s"
    main(["or-fetch", "--venue", VENUE, "--number", "42", "--session", str(sess)])
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "They addressed point one.")
    rc = main(["or-responses", "--session", str(sess)])
    assert rc == 0
    assert (sess / "ours" / "response-analysis.txt").read_text() == \
        "They addressed point one."


def test_or_responses_with_nothing_received_exits_2(tmp_path, capsys):
    s = Session.create(tmp_path, "s")
    rc = main(["or-responses", "--session", str(s.dir)])
    assert rc == 2
    assert "nothing to analyze" in capsys.readouterr().err


def test_or_draft_refuses_a_venue_that_prohibits_outside_models(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """or-fetch records the venue, so or-draft can enforce the venue's rule.

    A session fetched from a venue that forbids sending submissions to an
    outside model must not be drafted from, however the environment is set. The
    manuscript is already on disk at this point; the check has to sit in front
    of the send, not in front of the fetch.
    """
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    Session(sess).set_state("venue", "NeurIPS.cc/2026/Conference")
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_ZERO_RETENTION", "1")
    rc = main(["or-draft", "--session", str(sess)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "prohibits" in err.lower()
    assert not (sess / "ours" / "openreview.md").exists()
