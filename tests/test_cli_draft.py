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
    assert (s.dir / "drafts" / "report.txt").read_text() == "Eq. (3) is fine."
    assert "flag" in capsys.readouterr().out.lower()
