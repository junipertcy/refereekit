from refereekit.ingest import ingest, to_json, from_json
from refereekit.types import Document

def test_ingest_returns_document_with_pages(sample_doc):
    assert isinstance(sample_doc, Document)
    assert len(sample_doc.pages) >= 1
    assert any("prescribed degree-size sequences" in p.text.lower()
               or "degree-size" in p.text.lower() for p in sample_doc.pages)

def test_ingest_extracts_equations(sample_doc):
    # three numbered equations planted in the fixture
    assert len(sample_doc.equations) >= 1

def test_json_roundtrip(sample_doc):
    doc2 = from_json(to_json(sample_doc))
    assert doc2.page_text(1)[:20] == sample_doc.page_text(1)[:20]
