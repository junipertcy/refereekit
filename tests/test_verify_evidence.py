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
    assert verify(Claim("apple banana cherry", "page", "5"), _doc()).status == "FLAG"


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


def test_a_bare_pointer_to_a_nonexistent_page_fails():
    """Ordering matters, and the page comes first. A pointer to a page that is
    not in the document is a genuine FAIL, however little it quotes. Gating on
    the quotation first would report it FLAG, and FLAG means the citation is
    safe to keep, which would let a pointer to a nonexistent page into the
    claim pool."""
    v = verify(Claim("", "page", "9999"), _doc())
    assert v.status == "FAIL"
    assert "does not exist" in v.evidence


def test_flag_guarantees_the_page_exists():
    """FLAG is what licenses recording a bare pointer, so it has to promise
    more than 'unchecked': the page is confirmed present."""
    v = verify(Claim("", "page", "5"), _doc())
    assert v.status == "FLAG"
    assert "page 5 exists" in v.evidence


def test_verify_exit_codes_via_cli():
    """PASS=0, FAIL=1, FLAG=3 so calling scripts can distinguish outcomes."""
    from refereekit.cli import main
    import tempfile, json
    from pathlib import Path

    doc = _doc()
    with tempfile.TemporaryDirectory() as tmpdir:
        session = Path(tmpdir) / "session"
        session.mkdir()
        (session / "doc.json").write_text(json.dumps({
            "pages": [{"n": p.n, "text": p.text, "blocks": []} for p in doc.pages],
            "figures": [],
            "equations": [],
            "sections": []
        }))

        # PASS: verified text
        exit_code = main(["verify", "--session", str(session), "--kind", "page",
                         "--anchor", "5", "--text", "retains a spectral plateau"])
        assert exit_code == 0, "PASS should exit 0"

        # FAIL: contradicted
        exit_code = main(["verify", "--session", str(session), "--kind", "page",
                         "--anchor", "5", "--text", "no such phrase here at all"])
        assert exit_code == 1, "FAIL should exit 1"

        # FLAG: no quotation
        exit_code = main(["verify", "--session", str(session), "--kind", "page",
                         "--anchor", "5", "--text", "too short"])
        assert exit_code == 3, "FLAG should exit 3"
