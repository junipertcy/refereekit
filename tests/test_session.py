from refereekit.session import Session
from refereekit.types import Document, Page

def test_session_roundtrips_doc_and_state(tmp_path):
    s = Session.create(tmp_path, "paperA")
    doc = Document(pages=[Page(1, "hi", [])], figures=[], equations=[], sections=[])
    s.save_doc(doc)
    assert s.load_doc().page_text(1) == "hi"
    s.set_state("verdict", "major")
    assert Session(s.dir).get_state("verdict") == "major"
