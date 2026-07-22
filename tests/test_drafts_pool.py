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
