import os
from refereekit.cli import main
from refereekit.session import Session
from refereekit.types import Claim
from refereekit.ingest import ingest

def test_cli_draft_writes_report_offline(tmp_path, sample_pdf_path, capsys, monkeypatch):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(sample_pdf_path))
    s.record_claim(Claim("counting identity", "equation", "3"))
    s.set_state("verdict", {"recommend": "minor"})
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Eq. (3) is fine.")
    rc = main(["draft", "--session", str(s.dir)])
    assert rc == 0
    assert (s.dir / "ours" / "report.txt").read_text() == "Eq. (3) is fine."
    assert "flag" in capsys.readouterr().out.lower()


def test_draft_refuses_a_prohibited_venue(tmp_path, sample_pdf_path, monkeypatch,
                                          capsys):
    """draft has no --venue; the session recorded one, and that is enough."""
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(sample_pdf_path))
    s.record_claim(Claim("counting identity", "equation", "3"))
    s.set_state("verdict", {"recommend": "minor", "venue": "NeurIPS"})
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    rc = main(["draft", "--session", str(s.dir)])
    assert rc == 2
    assert "prohibits" in capsys.readouterr().err.lower()
    assert not (s.dir / "ours" / "report.txt").exists()


def test_editor_refuses_a_prohibited_venue(tmp_path, sample_pdf_path, monkeypatch,
                                           capsys):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(sample_pdf_path))
    s.record_claim(Claim("counting identity", "equation", "3"))
    s.set_state("venue", "NeurIPS.cc/2026/Conference")
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    rc = main(["editor", "--session", str(s.dir), "--answers", "a=yes"])
    assert rc == 2
    assert "prohibits" in capsys.readouterr().err.lower()
