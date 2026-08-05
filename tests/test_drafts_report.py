# tests/test_drafts_report.py
from refereekit.drafts import report, Draft, build_prompt, build_editor_prompt
from refereekit.llm import FakeBackend
from refereekit.session import Session
from refereekit.types import Claim

def _first_real_eq_id(doc):
    """Select first plausible low-numbered equation label, not scan-order-dependent."""
    cands = sorted(int(e.id) for e in doc.equations if e.id.isdigit() and 1 <= int(e.id) <= 12)
    return str(cands[0]) if cands else "1"

def _session_with_pool(tmp_path, real_doc):
    s = Session.create(tmp_path, "p")
    s.save_doc(real_doc)  # reuse the session-scoped ingested doc; no re-ingest
    eq_id = _first_real_eq_id(real_doc)
    s.record_claim(Claim("counting identity", "equation", eq_id))
    s.set_state("verdict", {"recommend": "minor"})
    return s

def test_report_keeps_valid_and_flags_invalid(tmp_path, real_doc):
    s = _session_with_pool(tmp_path, real_doc)
    eq_id = _first_real_eq_id(real_doc)
    # canned prose: one in-pool+valid anchor, one out-of-pool
    canned = f"The identity in Eq. ({eq_id}) is correct. However Eq. (99) is unsupported."
    d = report(s, s.get_state("verdict"), {}, backend=FakeBackend(canned), style_path="style/STYLE.md")
    assert isinstance(d, Draft)
    assert d.text == canned
    flagged = {(f.kind, f.anchor) for f in d.flags}
    assert ("equation", "99") in flagged      # out-of-pool AND fails verify -> flagged
    assert ("equation", eq_id) not in flagged   # in pool AND verifies -> kept

def test_prompt_contains_style_and_pool(tmp_path, real_doc):
    s = _session_with_pool(tmp_path, real_doc)
    seen = {}
    def capture(p): seen["p"] = p; return "ok"
    report(s, s.get_state("verdict"), {}, backend=FakeBackend(capture), style_path="style/STYLE.md")
    assert "The authors may consider" in seen["p"]   # STYLE.md content present
    eq_id = _first_real_eq_id(real_doc)
    assert eq_id in seen["p"]                         # pool claim anchor present

def test_prompt_contains_citation_format_instruction():
    pool = {"claims": [], "verdict": {}}
    prompt = build_prompt(pool, "test style", {})
    assert "Eq. (N)" in prompt or "Eq. (3)" in prompt  # instruction mentions Eq. (N) format
    assert "p. N" in prompt or "p. 16" in prompt       # instruction mentions p. N format
    assert "CITATION FORMAT" in prompt                  # explicit section header

def test_report_flags_failed_reverification(tmp_path, real_doc):
    """Test that an anchor IN the pool but failing re-verification is flagged."""
    s = Session.create(tmp_path, "p")
    s.save_doc(real_doc)
    # Record a claim for equation 99 (NOT in the real_doc)
    # This claim is in the pool, but re-verification will fail
    s.record_claim(Claim("nonexistent identity", "equation", "99"))
    canned = "The draft cites Eq. (99)."
    d = report(s, {}, {}, backend=FakeBackend(canned), style_path="style/STYLE.md")
    # Eq. (99) should be flagged because it's in pool but fails re-verification
    flagged = {(f.kind, f.anchor) for f in d.flags}
    assert ("equation", "99") in flagged
    # Check that the reason mentions failed verification (not "not in pool")
    eq99_flags = [f for f in d.flags if f.kind == "equation" and f.anchor == "99"]
    assert len(eq99_flags) == 1
    assert "failed" in eq99_flags[0].reason.lower() or "verify" in eq99_flags[0].reason.lower()

def test_report_with_memory_recall(tmp_path, real_doc):
    """Test that recalled notes appear in the draft prompt."""
    from refereekit.memory import SQLiteMemoryStore, Note
    from datetime import datetime, timezone

    s = _session_with_pool(tmp_path, real_doc)
    db_path = tmp_path / "test_mem.db"
    store = SQLiteMemoryStore(db_path)

    # Store a note for venue PRX with explicit created_at
    note_text = "PRX style: lean accept-after-major"
    created_at = datetime.now(timezone.utc).isoformat()
    store.store(Note(note_text, "PRX", "style", created_at=created_at), real_doc, created_at=created_at)

    # Capture the prompt
    seen = {}
    def capture(p): seen["p"] = p; return "draft text"

    d = report(s, s.get_state("verdict"), {},
               backend=FakeBackend(capture),
               style_path="style/STYLE.md",
               memory=store,
               venue="PRX")

    # Assert the recalled note text appears in the prompt
    assert note_text in seen["p"]
    assert "=== PRIOR NOTES" in seen["p"]
    assert isinstance(d, Draft)

def test_report_without_memory_still_works(tmp_path, real_doc):
    """Test that report() without memory/venue still works (backwards compat)."""
    s = _session_with_pool(tmp_path, real_doc)
    d = report(s, s.get_state("verdict"), {},
               backend=FakeBackend("draft text"),
               style_path="style/STYLE.md")
    assert isinstance(d, Draft)
    assert d.text == "draft text"


def test_prompt_shows_the_verified_quotation():
    pool = {"claims": [Claim("a spectral plateau of width W", "page", "7")],
            "verdict": {}}
    out = build_prompt(pool, "voice", {})
    assert "a spectral plateau of width W" in out
    assert "page (7)" in out


def test_prompt_separates_unverified_pointers():
    pool = {"claims": [Claim("a spectral plateau of width W", "page", "7"),
                       Claim("", "page", "15")],
            "verdict": {}}
    out = build_prompt(pool, "voice", {})
    assert "VERIFIED QUOTATIONS" in out
    assert "UNVERIFIED POINTERS" in out
    # The quotation appears under the verified heading, p.15 under the other.
    verified, unverified = out.split("UNVERIFIED POINTERS", 1)
    assert "page (7)" in verified
    assert "page (15)" in unverified
    assert "page (7)" not in unverified


def test_editor_prompt_shows_the_quotation_too():
    pool = {"claims": [Claim("a spectral plateau of width W", "page", "7")],
            "verdict": {}}
    out = build_editor_prompt(pool, "voice", {"a": "yes"})
    assert "a spectral plateau of width W" in out


def test_verify_prose_valid_quotation_in_pool():
    """Prose quoting text that IS on the page AND whose (kind, anchor) is in pool."""
    from refereekit.drafts import _verify_prose
    from refereekit.types import Document, Page, Claim

    page_text = "The numerical algorithm converges uniformly on compact domains."
    doc = Document(pages=[Page(n=3, text=page_text)])
    pool = {
        "claims": [Claim("converges uniformly on compact domains", "page", "3")],
        "verdict": {}
    }
    prose = 'The method "converges uniformly on compact domains" according to p. 3.'
    draft = _verify_prose(prose, pool, doc)
    assert draft.flags == []


def test_verify_prose_fabricated_quotation_caught():
    """Prose quoting a 4+ word phrase NOT on the cited page is caught by re-verification.

    This is the load-bearing test: fabricated quotations must produce a flag.
    """
    from refereekit.drafts import _verify_prose
    from refereekit.types import Document, Page, Claim

    page_text = "The numerical algorithm converges uniformly on compact domains."
    doc = Document(pages=[Page(n=3, text=page_text)])
    pool = {
        "claims": [Claim("diverges chaotically across all parameter spaces", "page", "3")],
        "verdict": {}
    }
    prose = 'The method "diverges chaotically across all parameter spaces" per p. 3.'
    draft = _verify_prose(prose, pool, doc)
    assert len(draft.flags) == 1
    assert draft.flags[0].kind == "page"
    assert draft.flags[0].anchor == "3"
    assert "failed re-verification" in draft.flags[0].reason


def test_verify_prose_anchor_not_in_pool():
    """Prose citing a page that is NOT in the verified pool."""
    from refereekit.drafts import _verify_prose
    from refereekit.types import Document, Page, Claim

    page_text = "The numerical algorithm converges uniformly on compact domains."
    doc = Document(pages=[Page(n=3, text=page_text), Page(n=5, text="Different content.")])
    pool = {
        "claims": [Claim("some verified content", "page", "5")],
        "verdict": {}
    }
    prose = 'The method "converges uniformly on compact domains" per p. 3.'
    draft = _verify_prose(prose, pool, doc)
    assert len(draft.flags) == 1
    assert draft.flags[0].kind == "page"
    assert draft.flags[0].anchor == "3"
    assert "not in verified pool" in draft.flags[0].reason


def test_verify_prose_bare_page_pointer_not_flagged():
    """Prose citing a page bare, with no quotation, where (kind, anchor) IS in pool.

    Bare pointers verify as FLAG (unverifiable), not FAIL, so they are never flagged.
    A page number without quotation is legitimate: it points to reference material
    but makes no factual claim, so there is nothing to verify as false.
    """
    from refereekit.drafts import _verify_prose
    from refereekit.types import Document, Page, Claim

    page_text = "The numerical algorithm converges uniformly on compact domains."
    doc = Document(pages=[Page(n=3, text=page_text)])
    pool = {
        "claims": [Claim("", "page", "3")],
        "verdict": {}
    }
    prose = 'See p. 3 for additional discussion.'
    draft = _verify_prose(prose, pool, doc)
    assert draft.flags == []
