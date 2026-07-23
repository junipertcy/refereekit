# tests/test_drafts_report.py
from refereekit.drafts import report, Draft, build_prompt
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
