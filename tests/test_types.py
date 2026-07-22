from refereekit.types import Document, Page, Claim, Verdict

def test_document_page_text_lookup():
    doc = Document(pages=[Page(n=1, text="hello", blocks=[]),
                          Page(n=2, text="world", blocks=[])],
                   figures=[], equations=[], sections=[])
    assert doc.page_text(2) == "world"

def test_document_page_text_missing_raises():
    doc = Document(pages=[], figures=[], equations=[], sections=[])
    try:
        doc.page_text(5); assert False
    except KeyError:
        pass

def test_claim_and_verdict_construct():
    c = Claim(text="5-8%", kind="quote", anchor="16")
    v = Verdict(status="PASS", evidence="found on page 16")
    assert c.kind == "quote" and v.status == "PASS"
