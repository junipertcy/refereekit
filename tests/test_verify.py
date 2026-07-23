from refereekit.verify import verify
from refereekit.types import Claim

def _first_real_eq_id(doc):
    """Select first plausible low-numbered equation label, not scan-order-dependent."""
    cands = sorted(int(e.id) for e in doc.equations if e.id.isdigit() and int(e.id) <= 12)
    return str(cands[0]) if cands else "1"

def test_quote_on_correct_page_passes(sample_doc):
    v = verify(Claim("prescribed degree-size sequences", "quote", "1"), sample_doc)
    assert v.status == "PASS"

def test_quote_on_wrong_page_fails(sample_doc):
    v = verify(Claim("prescribed degree-size sequences", "quote", "99"), sample_doc)
    assert v.status == "FAIL"

def test_existing_equation_passes(real_doc):
    # use real_doc which has equations extracted from right margin geometry
    eq_id = _first_real_eq_id(real_doc)
    v = verify(Claim("counting identity", "equation", eq_id), real_doc)
    assert v.status == "PASS"

def test_nonexistent_equation_fails(sample_doc):
    v = verify(Claim("nope", "equation", "9"), sample_doc)
    assert v.status == "FAIL"

def test_figure_claim_flags(sample_doc):
    v = verify(Claim("Realizability regions", "figure", "1"), sample_doc)
    assert v.status == "FLAG"
