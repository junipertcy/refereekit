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
    assert (tmp_path / "s" / "ours" / "report.txt").exists()
    assert (tmp_path / "s" / "ours" / "editor.txt").exists()

def test_cli_review_missing_pdf_exit2(tmp_path, monkeypatch):
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    rc = main(["review", str(tmp_path / "nope.pdf"), "--session", str(tmp_path / "s")])
    assert rc == 2

def test_cli_review_not_zero_retention_exits_2(tmp_path, monkeypatch, capsys):
    # Real backend path, but zero-retention NOT enabled -> RetentionError -> clean exit 2 (no traceback)
    monkeypatch.delenv("REFEREEKIT_FAKE", raising=False)
    monkeypatch.delenv("REFEREEKIT_ZERO_RETENTION", raising=False)
    # Mock AnthropicBackend to avoid network/import; still has zero_retention=False
    from refereekit.llm import FakeBackend
    mock_backend = FakeBackend("mock", zero_retention=False)  # key: zero_retention=False
    monkeypatch.setattr("refereekit.cli._backend", lambda: mock_backend)
    from refereekit.cli import main
    rc = main(["review", "tests/fixtures/real_paper.pdf", "--session", str(tmp_path / "s")])
    assert rc == 2
    assert "retention" in capsys.readouterr().err.lower()

def test_cli_review_with_venue_fresh_session(tmp_path, real_pdf_path, monkeypatch):
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Answer about the paper. See p. 1.")
    script = iter(["a question?", "", "minor revision", "PRX", "minor", "", ""])
    from refereekit.agent import run_review
    monkeypatch.setitem(run_review.__kwdefaults__, "input_fn", lambda _="": next(script))
    sess = tmp_path / "fresh"   # does NOT exist yet
    rc = main(["review", str(real_pdf_path), "--session", str(sess), "--venue", "PRX"])
    assert rc == 0
    assert (sess / "ours" / "report.txt").exists() and (sess / "ours" / "editor.txt").exists()
    assert (sess / "memory.db").exists()   # --venue created the store in the fresh dir
