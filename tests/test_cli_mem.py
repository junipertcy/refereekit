# tests/test_cli_mem.py
from refereekit.cli import main
from refereekit.session import Session
from refereekit.ingest import ingest

def _sess(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "s"); s.save_doc(ingest(real_pdf_path)); return s

def test_mem_store_then_recall(tmp_path, real_pdf_path, capsys):
    s = _sess(tmp_path, real_pdf_path)
    db = str(s.dir / "memory.db")
    rc = main(["mem-store", "--session", str(s.dir), "--venue", "PRX",
               "--kind", "verdict", "--text", "PRX: lean accept-after-major", "--db", db])
    assert rc == 0
    rc2 = main(["mem-recall", "--venue", "PRX", "--db", db])
    out = capsys.readouterr().out
    assert rc2 == 0 and "accept-after-major" in out

def test_mem_store_rejects_manuscript(tmp_path, real_pdf_path, capsys):
    s = _sess(tmp_path, real_pdf_path)
    db = str(s.dir / "memory.db")
    rc = main(["mem-store", "--session", str(s.dir), "--venue", "PRX",
               "--kind", "quote", "--text", "prescribed degree-size sequences", "--db", db])
    assert rc == 2
    assert "manuscript" in capsys.readouterr().err.lower()
