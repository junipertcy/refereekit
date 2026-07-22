# tests/test_drafts_report.py
from refereekit.drafts import report, Draft, build_prompt
from refereekit.llm import FakeBackend
from refereekit.session import Session
from refereekit.types import Claim
from refereekit.ingest import ingest

def _session_with_pool(tmp_path, sample_pdf_path):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(sample_pdf_path))
    s.record_claim(Claim("counting identity", "equation", "3"))  # exists in fixture
    s.set_state("verdict", {"recommend": "minor"})
    return s

def test_report_keeps_valid_and_flags_invalid(tmp_path, sample_pdf_path):
    s = _session_with_pool(tmp_path, sample_pdf_path)
    # canned prose: one in-pool+valid anchor (Eq 3), one out-of-pool (Eq 9, also absent from PDF)
    canned = "The identity in Eq. (3) is correct. However Eq. (9) is unsupported."
    d = report(s, s.get_state("verdict"), {}, backend=FakeBackend(canned), style_path="style/STYLE.md")
    assert isinstance(d, Draft)
    assert d.text == canned
    flagged = {(f.kind, f.anchor) for f in d.flags}
    assert ("equation", "9") in flagged      # out-of-pool AND fails verify -> flagged
    assert ("equation", "3") not in flagged   # in pool AND verifies -> kept

def test_prompt_contains_style_and_pool(tmp_path, sample_pdf_path):
    s = _session_with_pool(tmp_path, sample_pdf_path)
    seen = {}
    def capture(p): seen["p"] = p; return "ok"
    report(s, s.get_state("verdict"), {}, backend=FakeBackend(capture), style_path="style/STYLE.md")
    assert "The authors may consider" in seen["p"]   # STYLE.md content present
    assert "3" in seen["p"]                            # pool claim anchor present

def test_prompt_contains_citation_format_instruction():
    pool = {"claims": [], "verdict": {}}
    prompt = build_prompt(pool, "test style", {})
    assert "Eq. (N)" in prompt or "Eq. (3)" in prompt  # instruction mentions Eq. (N) format
    assert "p. N" in prompt or "p. 16" in prompt       # instruction mentions p. N format
    assert "CITATION FORMAT" in prompt                  # explicit section header

def test_report_flags_failed_reverification(tmp_path, sample_pdf_path):
    """Test that an anchor IN the pool but failing re-verification is flagged."""
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(sample_pdf_path))
    # Record a claim for equation 7 (NOT in the fixture, which has only 1,2,3)
    # This claim is in the pool, but re-verification will fail
    s.record_claim(Claim("nonexistent identity", "equation", "7"))
    canned = "The draft cites Eq. (7)."
    d = report(s, {}, {}, backend=FakeBackend(canned), style_path="style/STYLE.md")
    # Eq. (7) should be flagged because it's in pool but fails re-verification
    flagged = {(f.kind, f.anchor) for f in d.flags}
    assert ("equation", "7") in flagged
    # Check that the reason mentions failed verification (not "not in pool")
    eq7_flags = [f for f in d.flags if f.kind == "equation" and f.anchor == "7"]
    assert len(eq7_flags) == 1
    assert "failed" in eq7_flags[0].reason.lower() or "verify" in eq7_flags[0].reason.lower()
