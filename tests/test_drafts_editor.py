# tests/test_drafts_editor.py
from refereekit.drafts import editor_letter, Draft, build_editor_prompt
from refereekit.llm import FakeBackend
from refereekit.session import Session
from refereekit.types import Claim
from refereekit.ingest import ingest

def test_editor_letter_runs_pipeline_and_flags(tmp_path, sample_pdf_path):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(sample_pdf_path))
    s.record_claim(Claim("counting identity", "equation", "3"))
    canned = "a) Novelty: PARTLY. See Eq. (9) which is not in the paper."
    d = editor_letter(s, {"a": "novelty?"}, backend=FakeBackend(canned), style_path="style/STYLE.md")
    assert isinstance(d, Draft) and d.text == canned
    assert ("equation", "9") in {(f.kind, f.anchor) for f in d.flags}

def test_editor_prompt_includes_answers(tmp_path, sample_pdf_path):
    s = Session.create(tmp_path, "p"); s.save_doc(ingest(sample_pdf_path))
    seen = {}
    def cap(p): seen["p"] = p; return "ok"
    editor_letter(s, {"c": "impact question"}, backend=FakeBackend(cap), style_path="style/STYLE.md")
    assert "impact question" in seen["p"]

def test_editor_prompt_contains_citation_format_instruction():
    pool = {"claims": [], "verdict": {}}
    prompt = build_editor_prompt(pool, "test style", {"a": "test"})
    assert "Eq. (N)" in prompt or "Eq. (3)" in prompt  # instruction mentions Eq. (N) format
    assert "p. N" in prompt or "p. 16" in prompt       # instruction mentions p. N format
    assert "CITATION FORMAT" in prompt                  # explicit section header
