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
