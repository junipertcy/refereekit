import re
from .types import Claim, Verdict, Document

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def verify(claim: Claim, doc: Document) -> Verdict:
    if claim.kind in ("quote", "page"):
        try:
            page_no = int(claim.anchor)
        except ValueError:
            return Verdict("FAIL", f"anchor {claim.anchor!r} is not a page number")
        try:
            text = doc.page_text(page_no)
        except KeyError:
            return Verdict("FAIL", f"page {page_no} does not exist")
        if _norm(claim.text) in _norm(text):
            return Verdict("PASS", f"found on page {page_no}")
        return Verdict("FAIL", f"not found on page {page_no}")
    if claim.kind == "equation":
        if any(e.id == claim.anchor for e in doc.equations):
            return Verdict("PASS", f"equation ({claim.anchor}) exists")
        return Verdict("FAIL", f"equation ({claim.anchor}) not found")
    # figure + unknown -> semantic, needs human/LLM
    return Verdict("FLAG", f"'{claim.kind}' claim needs human confirmation")
