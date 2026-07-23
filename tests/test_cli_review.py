import os
from refereekit.cli import main

def test_cli_review_end_to_end_offline(tmp_path, real_pdf_path, monkeypatch):
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Answer about the paper. See p. 1.")
    script = iter(["a question?", "", "minor revision", "PRX", "minor", "", ""])
    # Patch the function's default argument directly
    from refereekit.agent import run_review
    original_defaults = run_review.__defaults__
    new_input = lambda _="": next(script)
    # __defaults__ is a tuple: (backend, session_dir, input_fn, output_fn, style_path, memory, venue)
    # input_fn is at index 2 (0=backend, 1=session_dir, 2=input_fn, 3=output_fn)
    # Wait, these are keyword-only args, need to use __kwdefaults__ instead
    monkeypatch.setitem(run_review.__kwdefaults__, "input_fn", new_input)
    rc = main(["review", str(real_pdf_path), "--session", str(tmp_path / "s")])
    assert rc == 0
    assert (tmp_path / "s" / "report.txt").exists()
    assert (tmp_path / "s" / "editor.txt").exists()

def test_cli_review_missing_pdf_exit2(tmp_path, monkeypatch):
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    rc = main(["review", str(tmp_path / "nope.pdf"), "--session", str(tmp_path / "s")])
    assert rc == 2
