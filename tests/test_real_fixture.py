from refereekit.types import Document

def test_real_paper_ingests(real_doc):
    assert isinstance(real_doc, Document)
    assert len(real_doc.pages) == 9
    assert "simplicial complexes" in real_doc.page_text(1).lower()
