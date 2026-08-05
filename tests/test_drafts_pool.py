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


def test_same_page_quoted_and_bare():
    """A page cited both with and without a quotation yields both claims."""
    prose = 'The estimator "dampens residuals" on p. 7. See also p. 7.'
    claims = [c for c in extract_anchors(prose) if c.kind == "page"]
    assert len(claims) == 2
    texts = sorted(c.text for c in claims)
    assert texts == ["", "dampens residuals"]
    assert all(c.anchor == "7" for c in claims)


def test_page_inside_quotation_creates_bare_claim():
    """A page number appearing inside a quotation yields a bare claim.

    This pins the behavior that p.7 inside the quote is not consumed by the
    quote's pairing to p.9, so p.7 surfaces as a bare (unverified) claim.
    However, this test passes even with the old broken code, so it documents
    behavior rather than catching the fix."""
    prose = 'They write "as shown on p. 7 the bound holds" on p. 9.'
    claims = [c for c in extract_anchors(prose) if c.kind == "page"]
    assert len(claims) == 2
    anchors = {c.anchor for c in claims}
    assert anchors == {"7", "9"}
