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
    prompts = []
    def backend_fn(p):
        prompts.append(p)
        return "Contribution summarized. See p. 1."
    outputs = []
    res = run_review(real_pdf_path, backend=FakeBackend(backend_fn),
                     session_dir=tmp_path / "s",
                     input_fn=lambda _="": next(script), output_fn=outputs.append,
                     memory=mem, venue="PRX")
    assert isinstance(res, ReviewResult)
    assert res.report_path.exists() and res.editor_path.exists()
    assert res.verdict["venue"] == "PRX"
    assert res.report_path.read_text()  # non-empty draft
    # summary step ran and was emitted as the first output, distinct from Q&A
    assert outputs[0].startswith("SUMMARY:")
    # recalled note threaded into BOTH the report and the editor prompt (SP-C wiring)
    report_prompts = [p for p in prompts if "=== SECTION LENGTHS ===" in p]
    editor_prompts = [p for p in prompts if "=== EDITOR QUESTIONS" in p]
    assert report_prompts and "lean accept-after-major" in report_prompts[0]
    assert editor_prompts and "lean accept-after-major" in editor_prompts[0]
