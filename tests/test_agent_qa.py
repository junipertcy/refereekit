from refereekit.agent.loop import _qa_loop
from refereekit.session import Session
from refereekit.ingest import ingest
from refereekit.llm import FakeBackend

def test_qa_records_verified_anchor_and_appends_html(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "p"); doc = ingest(real_pdf_path); s.save_doc(doc)
    # canned answer cites a real equation (3 exists) and a bogus one (99)
    canned = "The identity in Eq. (3) holds; Eq. (99) does not."
    out = []
    script = iter(["what is the key result?", ""])   # one question then sentinel
    tr = _qa_loop(s, doc, backend=FakeBackend(canned),
                  input_fn=lambda _="": next(script), output_fn=out.append)
    assert len(tr) == 1 and tr[0][0] == "what is the key result?"
    # verified anchor recorded to session pool; bogus one not
    anchors = {(c.kind, c.anchor) for c in Session(s.dir).verified_claims()}
    assert ("equation", "3") in anchors
    assert ("equation", "99") not in anchors
    assert (s.dir / "index.html").exists()   # render wrote the page
    assert any("Eq. (3)" in o for o in out)  # answer emitted
    assert any("unverified" in o.lower() for o in out)   # flagged to the referee, not silently dropped

def test_qa_sentinel_first_yields_empty_transcript(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "p"); doc = ingest(real_pdf_path); s.save_doc(doc)
    tr = _qa_loop(s, doc, backend=FakeBackend("x"),
                  input_fn=lambda _="": "", output_fn=lambda _:None)
    assert tr == []
