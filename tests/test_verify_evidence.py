from refereekit.types import Claim, Document, Page, MIN_EVIDENCE_WORDS
from refereekit.verify import verify


def _doc():
    return Document(pages=[Page(n=5, text="The estimator retains a spectral plateau of width W.")])


def test_min_evidence_words_is_four():
    assert MIN_EVIDENCE_WORDS == 4


def test_empty_text_page_claim_is_flagged_not_passed():
    """'' is a substring of every page, so this must never be PASS."""
    v = verify(Claim("", "page", "5"), _doc())
    assert v.status == "FLAG"
    assert "no quotation" in v.evidence


def test_whitespace_only_text_is_flagged():
    assert verify(Claim("   \n  ", "page", "5"), _doc()).status == "FLAG"


def test_too_short_text_is_flagged():
    """Three words can collide by accident; four is the floor."""
    assert verify(Claim("the kernel has", "page", "5"), _doc()).status == "FLAG"


def test_real_quote_passes():
    assert verify(Claim("retains a spectral plateau", "page", "5"), _doc()).status == "PASS"


def test_quote_absent_from_page_fails():
    """A long quotation that is not there is a genuine FAIL, not a FLAG."""
    v = verify(Claim("no such phrase appears here", "page", "5"), _doc())
    assert v.status == "FAIL"


def test_nonexistent_page_still_fails_even_with_a_real_quote():
    v = verify(Claim("retains a spectral plateau", "page", "9999"), _doc())
    assert v.status == "FAIL"
    assert "does not exist" in v.evidence


def test_short_text_is_flagged_before_the_page_is_checked():
    """Ordering matters: 'no quotation' is the more useful diagnosis."""
    v = verify(Claim("", "page", "9999"), _doc())
    assert v.status == "FLAG"
