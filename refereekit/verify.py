import difflib
from .textnorm import collapse as _norm, line_break_readings
from .types import Claim, Verdict, Document, MIN_EVIDENCE_WORDS

# Below this the nearest line resembles nothing and printing it is noise.
_NEAREST_CUTOFF = 0.6
_NEAREST_MAX_CHARS = 120


def _nearest_line(text: str, needle: str) -> str | None:
    """The line most like the claim, to say why it failed.

    A bare "not found on page 7" leaves the referee to re-read the page by eye,
    which is the work being automated. The nearest line distinguishes a slip in
    transcription from words that are genuinely absent. It is a diagnostic only
    and never changes the verdict.
    """
    best, score = None, 0.0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        r = difflib.SequenceMatcher(None, needle, _norm(line)).ratio()
        if r > score:
            best, score = line, r
    if best is None or score < _NEAREST_CUTOFF:
        return None
    return (best[:_NEAREST_MAX_CHARS] + "…"
            if len(best) > _NEAREST_MAX_CHARS else best)


def _vouched_run(doc: Document) -> int:
    """Highest equation number extraction can vouch for.

    Equation ids come from right-margin geometry, which yields real labels and
    noise indiscriminately: the sample paper here gives 1..7 alongside 18, 500
    and eleven others. Papers number equations from 1, so the unbroken run
    1,2,3,... that were all extracted bounds the range where PASS means
    something.

    Returns 0 when (1) itself was not extracted. Anchoring on the lowest id
    present instead would let a single low noise value become the floor and drag
    a false run up behind it; refusing everything is the safe direction.
    """
    ids = {int(e.id) for e in doc.equations if e.id.isdigit()}
    top = 0
    while top + 1 in ids:
        top += 1
    return top


def verify(claim: Claim, doc: Document) -> Verdict:
    if claim.kind in ("quote", "page"):
        # The page is checked first so that FLAG can carry a guarantee: the
        # page exists, only the wording is unchecked. Gating on the quotation
        # first would FLAG a citation to a page that is not in the document,
        # which is a genuine FAIL and must not be reported as unverifiable.
        try:
            page_no = int(claim.anchor)
        except ValueError:
            return Verdict("FAIL", f"anchor {claim.anchor!r} is not a page number")
        try:
            text = doc.page_text(page_no)
        except KeyError:
            return Verdict("FAIL", f"page {page_no} does not exist")
        needle = _norm(claim.text)
        words = needle.split()
        if len(words) < MIN_EVIDENCE_WORDS:
            return Verdict("FLAG", f"page {page_no} exists; no quotation to "
                                   f"verify: {len(words)} words, need "
                                   f"{MIN_EVIDENCE_WORDS}")
        if any(needle in _norm(r) for r in line_break_readings(text)):
            return Verdict("PASS", f"found on page {page_no}")
        near = _nearest_line(text, needle)
        if near:
            return Verdict("FAIL", f"not found on page {page_no}; "
                                   f"nearest line is: {near!r}")
        return Verdict("FAIL", f"not found on page {page_no}")
    if claim.kind == "equation":
        extracted = any(e.id == claim.anchor for e in doc.equations)
        if not claim.anchor.isdigit():
            # Section-numbered labels ("2.1") are outside the run rule, which is
            # numeric. Existing behaviour, kept deliberately and documented as a
            # residual rather than changed silently.
            if extracted:
                return Verdict("PASS", f"equation ({claim.anchor}) exists")
            return Verdict("FAIL", f"equation ({claim.anchor}) not found")
        top = _vouched_run(doc)
        if 1 <= int(claim.anchor) <= top:
            return Verdict("PASS", f"equation ({claim.anchor}) exists")
        if extracted:
            # It was extracted, so "not found" would be a lie; it simply sits
            # where the extractor's output cannot be trusted.
            where = f"(1-{top})" if top else "(none confirmed)"
            return Verdict("FAIL", f"equation ({claim.anchor}) is outside the "
                                   f"range extraction can vouch for {where}")
        return Verdict("FAIL", f"equation ({claim.anchor}) not found")
    if claim.kind == "figure":
        if any(f.id == claim.anchor for f in doc.figures):
            return Verdict("PASS", f"figure ({claim.anchor}) exists")
        return Verdict("FAIL", f"figure ({claim.anchor}) not found")
    # unknown kinds -> semantic, needs human/LLM
    return Verdict("FLAG", f"'{claim.kind}' claim needs human confirmation")
