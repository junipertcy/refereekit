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

SPEC = '''
venue = "PRX"
questions = ["Where does the derivation stop being exact?"]

[verdict]
recommend = """
Publish after major revision.
MAJOR ISSUE 1: the Ansatz is uncontrolled and the error is never bounded.
"""
venue = "PRX"
major_minor = "major"

[editor_answers]
a = "PARTLY. The reduction is a real advance but the central step is an ansatz."
'''


def test_cli_review_runs_from_a_spec_with_no_typed_input(tmp_path, real_pdf_path,
                                                         monkeypatch):
    """A spec drives every gate, so the run needs no terminal and no input hack.

    The other tests here patch run_review.__kwdefaults__ to smuggle answers in.
    That hack exists only because the CLI had no way to script a review; --spec
    is that way, so this test uses none.
    """
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Answer about the paper. See p. 1.")
    spec = tmp_path / "review.toml"
    spec.write_text(SPEC)
    sess = tmp_path / "s"
    rc = main(["review", str(real_pdf_path), "--session", str(sess),
               "--spec", str(spec)])
    assert rc == 0
    assert (sess / "ours" / "report.txt").exists()
    assert (sess / "ours" / "editor.txt").exists()


def test_cli_review_spec_supplies_the_venue(tmp_path, real_pdf_path, monkeypatch):
    """A spec that names its venue does not also need --venue on the command line."""
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Answer about the paper. See p. 1.")
    spec = tmp_path / "review.toml"
    spec.write_text(SPEC)
    sess = tmp_path / "s"
    rc = main(["review", str(real_pdf_path), "--session", str(sess),
               "--spec", str(spec)])
    assert rc == 0
    assert (sess / "memory.db").exists()   # only created when a venue is in play


def test_cli_review_bad_spec_exits_2(tmp_path, real_pdf_path, monkeypatch, capsys):
    """A spec missing its verdict must fail before the manuscript is sent."""
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    spec = tmp_path / "review.toml"
    spec.write_text('questions = ["q"]\n')
    rc = main(["review", str(real_pdf_path), "--session", str(tmp_path / "s"),
               "--spec", str(spec)])
    assert rc == 2
    assert "verdict" in capsys.readouterr().err.lower()


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
