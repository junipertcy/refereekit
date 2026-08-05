# tests/test_cli.py
from refereekit.cli import main

def test_cli_ingest_then_verify(tmp_path, sample_pdf_path, capsys):
    sess = tmp_path / "s"
    assert main(["ingest", str(sample_pdf_path), "--session", str(sess)]) == 0
    assert (sess / "doc.json").exists()
    # a true quote on page 1 -> PASS, exit 0
    rc = main(["verify", "--session", str(sess), "--kind", "quote",
               "--anchor", "1", "--text", "Construction of Simplicial Complexes with Prescribed"])
    out = capsys.readouterr().out
    assert rc == 0 and "PASS" in out
    # a false quote -> FAIL, exit 1
    rc2 = main(["verify", "--session", str(sess), "--kind", "quote",
                "--anchor", "1", "--text", "this sentence is not in the paper at all"])
    assert rc2 == 1 and "FAIL" in capsys.readouterr().out

def test_cli_input_errors_exit_2(tmp_path, capsys):
    # missing session dir on verify -> exit 2
    rc = main(["verify", "--session", str(tmp_path / "does-not-exist"),
               "--kind", "quote", "--anchor", "1", "--text", "x"])
    assert rc == 2
    # missing PDF on ingest -> exit 2
    rc2 = main(["ingest", str(tmp_path / "missing.pdf"),
                "--session", str(tmp_path / "s")])
    assert rc2 == 2
