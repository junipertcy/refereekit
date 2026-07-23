import os
from refereekit.cli import main

def test_cli_review_end_to_end_offline(tmp_path, real_pdf_path, monkeypatch):
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Answer about the paper. See p. 1.")
    script = iter(["a question?", "", "minor revision", "PRX", "minor", "", ""])
    from refereekit.agent import run_review
    new_input = lambda _="": next(script)
    # Inject scripted input via run_review's keyword default (CLI itself passes no input_fn)
    monkeypatch.setitem(run_review.__kwdefaults__, "input_fn", new_input)
    rc = main(["review", str(real_pdf_path), "--session", str(tmp_path / "s")])
    assert rc == 0
    assert (tmp_path / "s" / "report.txt").exists()
    assert (tmp_path / "s" / "editor.txt").exists()

def test_cli_review_missing_pdf_exit2(tmp_path, monkeypatch):
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    rc = main(["review", str(tmp_path / "nope.pdf"), "--session", str(tmp_path / "s")])
    assert rc == 2
