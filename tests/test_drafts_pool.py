# tests/test_drafts_pool.py
from refereekit.drafts import build_pool, extract_anchors
from refereekit.session import Session
from refereekit.types import Claim

def test_build_pool_gathers_claims_and_verdict(tmp_path):
    s = Session.create(tmp_path, "p")
    s.record_claim(Claim("counting identity", "equation", "3"))
    s.set_state("verdict", {"recommend": "major"})
    pool = build_pool(s)
    assert pool["verdict"]["recommend"] == "major"
    assert pool["claims"][0].anchor == "3"

def test_extract_anchors_finds_page_and_equation():
    text = "As shown on p. 16 and in Eq. (3), the result holds."
    got = {(c.kind, c.anchor) for c in extract_anchors(text)}
    assert ("page", "16") in got
    assert ("equation", "3") in got

def test_extract_anchors_dedupes():
    text = "Eq. (3) ... again Eq. (3)."
    assert len(extract_anchors(text)) == 1


def test_quoted_page_claim_carries_the_quotation():
    prose = 'The estimator "dampens all residual couplings in that regime" on p. 7.'
    claims = [c for c in extract_anchors(prose) if c.kind == "page"]
    assert len(claims) == 1
    assert claims[0].anchor == "7"
    assert claims[0].text == "dampens all residual couplings in that regime"


def test_unquoted_page_claim_has_no_text():
    """Paraphrase carries no quotation, so there is nothing to verify."""
    prose = "The spike eigenvalue is order P, see p. 7."
    claims = [c for c in extract_anchors(prose) if c.kind == "page"]
    assert len(claims) == 1
    assert claims[0].text == ""


def test_equation_anchor_needs_no_quotation():
    claims = [c for c in extract_anchors("As Eq. (25) shows.") if c.kind == "equation"]
    assert len(claims) == 1
    assert claims[0].text == ""


def test_two_quotes_two_page_claims():
    prose = ('First "the lower band remains order one" on p. 3. '
             'Then "a spectral plateau of width W" on p. 7.')
    got = {c.anchor: c.text for c in extract_anchors(prose) if c.kind == "page"}
    assert got["3"] == "the lower band remains order one"
    assert got["7"] == "a spectral plateau of width W"
