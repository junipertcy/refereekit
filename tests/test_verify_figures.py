from refereekit.verify import verify
from refereekit.types import Claim

def test_existing_figure_passes(real_doc):
    v = verify(Claim("", "figure", "1"), real_doc)
    assert v.status == "PASS"

def test_absent_figure_fails(real_doc):
    v = verify(Claim("", "figure", "9"), real_doc)
    assert v.status == "FAIL"

def test_unknown_kind_still_flags(real_doc):
    v = verify(Claim("", "table", "1"), real_doc)
    assert v.status == "FLAG"
