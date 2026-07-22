import re
from .types import Document

class ManuscriptLeakError(ValueError):
    pass

def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}

def assert_no_manuscript(text: str, doc: Document, *, n: int = 8, max_overlap: int = 1) -> None:
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
