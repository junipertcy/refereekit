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
    assert any("CITATION FAILED" in o for o in out)   # bogus equation is a FAIL, not FLAG

def test_qa_sentinel_first_yields_empty_transcript(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "p"); doc = ingest(real_pdf_path); s.save_doc(doc)
    tr = _qa_loop(s, doc, backend=FakeBackend("x"),
                  input_fn=lambda _="": "", output_fn=lambda _:None)
    assert tr == []
def test_qa_records_a_bare_page_pointer(tmp_path, real_pdf_path):
    """A citation with no quotation still enters the pool. Its page exists, so
    the report may cite it; only the wording is unchecked. Leaving it out is
    what made a later draft flag correct prose as "not in verified pool"."""
    s = Session.create(tmp_path, "p"); doc = ingest(real_pdf_path); s.save_doc(doc)
    # p. 999 is inside the anchor pattern's 1-3 digit range but not in the PDF.
    canned = "The construction is described on p. 3, and p. 999 is not a page."
    out = []
    script = iter(["where is the construction?", ""])
    _qa_loop(s, doc, backend=FakeBackend(canned),
             input_fn=lambda _="": next(script), output_fn=out.append)
    anchors = {(c.kind, c.anchor) for c in Session(s.dir).verified_claims()}
    assert ("page", "3") in anchors        # page exists, wording unchecked
    assert ("page", "999") not in anchors  # page absent: a FAIL, never pooled
    assert any("unquoted, not verified" in o for o in out)
    assert any("CITATION FAILED" in o for o in out)
