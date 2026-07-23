import re
from .types import Document

class ManuscriptLeakError(ValueError):
    pass

def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}

def is_verbatim_fragment(text: str, doc: Document, *, n: int = 8) -> bool:
    words = re.findall(r"\w+", text)
    if len(words) >= n:
        return False
    norm = _normalize(text)
    if not norm:
        return False
    return any(norm in _normalize(p.text) for p in doc.pages)

def assert_no_manuscript(text: str, doc: Document, *, n: int = 8, max_overlap: int = 1) -> None:
    if is_verbatim_fragment(text, doc, n=n):
        raise ManuscriptLeakError(
            f"input is a verbatim manuscript fragment (<{n} words)"
        )
    q = _ngrams(text, n)
    if not q:
        return
    doc_ngrams: set[tuple[str, ...]] = set()
    for p in doc.pages:
        doc_ngrams |= _ngrams(p.text, n)
    overlap = len(q & doc_ngrams)
    if overlap > max_overlap:
        raise ManuscriptLeakError(
            f"input overlaps manuscript by {overlap} {n}-grams (max {max_overlap})"
        )
