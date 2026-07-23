from refereekit.agent import run_review, ReviewResult
from refereekit.llm import FakeBackend
from refereekit.memory import SQLiteMemoryStore, Note
from refereekit.ingest import ingest

def test_run_review_end_to_end(tmp_path, real_pdf_path):
    mem = SQLiteMemoryStore(tmp_path / "m.db")
    mem.store(Note("PRX: lean accept-after-major", "PRX"), ingest(real_pdf_path),
              created_at="2026-01-01T00:00:00")
    # scripted inputs: one question, sentinel, verdict(3), section-lengths blank,
    # editor answer key + value + blank-to-end
    script = iter([
        "what is the main contribution?", "",          # Q&A
        "major revision", "PRX", "major",              # verdict gate
        "",                                            # detail gate (default)
        "a", "novelty is partial", "",                 # editor answers
    ])
    outputs = []
    res = run_review(real_pdf_path, backend=FakeBackend("Contribution summarized. See p. 1."),
                     session_dir=tmp_path / "s",
                     input_fn=lambda _="": next(script), output_fn=outputs.append,
                     memory=mem, venue="PRX")
    assert isinstance(res, ReviewResult)
    assert res.report_path.exists() and res.editor_path.exists()
    assert res.verdict["venue"] == "PRX"
    assert res.report_path.read_text()  # non-empty draft
    assert any("summar" in o.lower() or "Contribution" in o for o in outputs)  # summary emitted
