import re
from .types import Document

class ManuscriptLeakError(ValueError):
    pass

def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}

def _normalize_words(text: str) -> str:
    """Normalize text to space-joined lowercase words for verbatim matching."""
    return " ".join(re.findall(r"\w+", text.lower()))

def is_verbatim_fragment(text: str, doc: Document, *, n: int = 8) -> bool:
    words = re.findall(r"\w+", text)

    # (a) Existing behavior: short text (< n words) checked as-is
    if len(words) < n:
        norm = _normalize(text)
        if not norm:
            return False
        return any(norm in _normalize(p.text) for p in doc.pages)

    # (b) New behavior: long text (>= n words) checked for embedded n-word runs
    # Cache normalized page strings for efficiency
    normalized_pages = [_normalize_words(p.text) for p in doc.pages]

    # Check each n-word window
    for i in range(len(words) - n + 1):
        window = " ".join(words[i:i+n]).lower()
        if any(window in page_text for page_text in normalized_pages):
            return True

    return False

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
