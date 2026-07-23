# tests/test_drafts_report.py
from refereekit.drafts import report, Draft, build_prompt
from refereekit.llm import FakeBackend
from refereekit.session import Session
from refereekit.types import Claim
from refereekit.ingest import ingest

def _session_with_pool(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(real_pdf_path))
    # Use real_doc which has equations from right-margin geometry
    doc = ingest(real_pdf_path)
    eq_id = doc.equations[0].id if doc.equations else "1"  # use first available or fallback
    s.record_claim(Claim("counting identity", "equation", eq_id))
    s.set_state("verdict", {"recommend": "minor"})
    return s

def test_report_keeps_valid_and_flags_invalid(tmp_path, real_pdf_path):
    s = _session_with_pool(tmp_path, real_pdf_path)
    doc = ingest(real_pdf_path)
    eq_id = doc.equations[0].id if doc.equations else "1"
    # canned prose: one in-pool+valid anchor, one out-of-pool
    canned = f"The identity in Eq. ({eq_id}) is correct. However Eq. (99) is unsupported."
    d = report(s, s.get_state("verdict"), {}, backend=FakeBackend(canned), style_path="style/STYLE.md")
    assert isinstance(d, Draft)
    assert d.text == canned
    flagged = {(f.kind, f.anchor) for f in d.flags}
    assert ("equation", "99") in flagged      # out-of-pool AND fails verify -> flagged
    assert ("equation", eq_id) not in flagged   # in pool AND verifies -> kept

def test_prompt_contains_style_and_pool(tmp_path, real_pdf_path):
    s = _session_with_pool(tmp_path, real_pdf_path)
    seen = {}
    def capture(p): seen["p"] = p; return "ok"
    report(s, s.get_state("verdict"), {}, backend=FakeBackend(capture), style_path="style/STYLE.md")
    assert "The authors may consider" in seen["p"]   # STYLE.md content present
    doc = ingest(real_pdf_path)
    eq_id = doc.equations[0].id if doc.equations else "1"
    assert eq_id in seen["p"]                         # pool claim anchor present

def test_prompt_contains_citation_format_instruction():
    pool = {"claims": [], "verdict": {}}
    prompt = build_prompt(pool, "test style", {})
    assert "Eq. (N)" in prompt or "Eq. (3)" in prompt  # instruction mentions Eq. (N) format
    assert "p. N" in prompt or "p. 16" in prompt       # instruction mentions p. N format
    assert "CITATION FORMAT" in prompt                  # explicit section header

def test_report_flags_failed_reverification(tmp_path, real_pdf_path):
    """Test that an anchor IN the pool but failing re-verification is flagged."""
    s = Session.create(tmp_path, "p")
    doc = ingest(real_pdf_path)
    s.save_doc(doc)
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
