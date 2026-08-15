"""An equation anchor passes only where extraction can vouch for it.

Equation ids come from right-margin geometry, which is best-effort: on the real
fixture it yields twenty numeric ids of which seven are labels. The other
thirteen -- 18, 19, 20, 22, 30, 39, 44, 50, 55, 82, 311, 490, 500 -- are noise,
and `verify --kind equation --anchor 500` returned PASS.

That is the dangerous direction. A false FAIL costs an argument with the tool; a
false PASS puts a citation to an equation that does not exist into a report
going to an editor under the referee's name.
"""
from refereekit.types import Claim, Document, Equation
from refereekit.verify import verify


def _doc(*ids: int) -> Document:
    return Document(pages=[],
                    equations=[Equation(id=str(i), page=1, body="") for i in ids])


def _v(doc: Document, anchor) -> str:
    return verify(Claim("some equation", "equation", str(anchor)), doc).status


# --- the contiguous run ------------------------------------------------------

def test_an_id_inside_the_run_passes():
    assert _v(_doc(1, 2, 3, 4, 5, 6, 7, 18, 500), 7) == "PASS"


def test_an_id_above_the_run_fails():
    assert _v(_doc(1, 2, 3, 4, 5, 6, 7, 18, 500), 500) == "FAIL"


def test_a_gap_ends_the_run():
    """18 is extracted, but 4..17 are not, so the run stops at 3."""
    assert _v(_doc(1, 2, 3, 18, 19, 20), 3) == "PASS"
    assert _v(_doc(1, 2, 3, 18, 19, 20), 18) == "FAIL"


def test_a_document_with_no_equations_passes_nothing():
    assert _v(_doc(), 1) == "FAIL"


def test_a_run_that_does_not_start_at_one_passes_nothing():
    """Papers number equations from 1. If (1) was never extracted there is no
    floor to trust, and anchoring on the lowest id would let a low noise value
    drag a false run up behind it."""
    assert _v(_doc(4, 5, 6), 5) == "FAIL"


def test_an_id_never_extracted_fails():
    assert _v(_doc(1, 2, 3), 9) == "FAIL"


# --- FAIL, never FLAG --------------------------------------------------------

def test_an_out_of_run_id_is_never_flagged():
    """FLAG is not the neutral middle it looks like.

    agent/loop.py records FLAG anchors into the claim pool on purpose, so that a
    bare page pointer stays citable. An equation id admitted on those terms is
    available to the draft with only a soft note -- nearly as harmful as PASS
    and easier to miss. FAIL keeps it out of the pool.
    """
    assert _v(_doc(1, 2, 3, 500), 500) != "FLAG"
    assert _v(_doc(1, 2, 3), 9) != "FLAG"


# --- the two refusals are distinguishable ------------------------------------

def test_evidence_separates_untrusted_range_from_absent_id():
    doc = _doc(1, 2, 3, 4, 5, 6, 7, 500)
    outside = verify(Claim("x", "equation", "500"), doc).evidence
    absent = verify(Claim("x", "equation", "9"), doc).evidence
    assert outside != absent
    assert "1-7" in outside          # names the range that can be vouched for
    assert "not found" in absent


# --- the real paper, as a regression pin -------------------------------------

def test_the_real_paper_passes_its_labels_and_rejects_its_noise(real_doc):
    """Pins the fixture's own noise so a change to ingest cannot quietly widen
    what verification will assert."""
    for real in range(1, 8):
        assert _v(real_doc, real) == "PASS", f"equation ({real}) is a real label"
    for noise in (18, 19, 20, 22, 30, 39, 44, 50, 55, 82, 311, 490, 500):
        assert _v(real_doc, noise) == "FAIL", f"equation ({noise}) is noise"


# --- unchanged behaviour ------------------------------------------------------

def test_a_non_numeric_anchor_keeps_existing_behaviour():
    """Section-numbered labels are outside the run rule, which is numeric.
    Documented as a residual rather than silently changed."""
    doc = Document(pages=[],
                   equations=[Equation(id="2.1", page=1, body="")])
    assert _v(doc, "2.1") == "PASS"
    assert _v(doc, "9.9") == "FAIL"
