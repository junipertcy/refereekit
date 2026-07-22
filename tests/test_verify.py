from refereekit.verify import verify
from refereekit.types import Claim

def test_quote_on_correct_page_passes(sample_doc):
    v = verify(Claim("prescribed degree-size sequences", "quote", "1"), sample_doc)
    assert v.status == "PASS"

def test_quote_on_wrong_page_fails(sample_doc):
    v = verify(Claim("prescribed degree-size sequences", "quote", "99"), sample_doc)
    assert v.status == "FAIL"

def test_existing_equation_passes(sample_doc):
    v = verify(Claim("counting identity", "equation", "3"), sample_doc)
    assert v.status == "PASS"

def test_nonexistent_equation_fails(sample_doc):
    v = verify(Claim("nope", "equation", "9"), sample_doc)
    assert v.status == "FAIL"

def test_figure_claim_flags(sample_doc):
    v = verify(Claim("Realizability regions", "figure", "1"), sample_doc)
    assert v.status == "FLAG"
