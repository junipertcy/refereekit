"""Find the quotations in generated prose and pair them with page citations.

Only text the author presented as a quotation is a candidate for substring
verification. Referee prose paraphrases the manuscript; it does not reproduce
it. Verifying a whole sentence against the page would fail on every honest
paraphrase, so this module narrows verification to quoted spans.
"""
import re

# Quoted spans shorter than this are scare-quoting, not evidence: a short
# phrase collides by accident and cannot carry a page claim.
MIN_QUOTE_CHARS = 12

# Straight or curly quotes around 1-400 characters. Match balanced pairs first;
# the length floor is applied in Python to avoid parity inversion.
_QUOTED = re.compile(r'["“]([^"”]{1,400})["”]')

_PAGE_ANCHOR = re.compile(r"(?:\bp\.?\s*|\bpage\s+)(\d{1,3})\b", re.I)


def quoted_spans(prose: str) -> list[tuple[int, int, str]]:
    """Return (start, end, text) for each quotation in `prose`.

    Offsets bound the quoted text itself, not the surrounding quote marks.
    """
    out = []
    for m in _QUOTED.finditer(prose):
        raw = m.group(1)
        lead = len(raw) - len(raw.lstrip())
        text = raw.strip()
        if not text or len(text) < MIN_QUOTE_CHARS:
            continue
        start = m.start(1) + lead
        out.append((start, start + len(text), text))
    return out


def _nearest(anchors, start, end):
    """Index of the anchor closest to the span; 0 distance if it sits inside."""
    return min(range(len(anchors)),
               key=lambda i: 0 if start <= anchors[i][0] <= end
               else min(abs(anchors[i][0] - end), abs(start - anchors[i][0])))


def pair_with_pages(prose: str) -> list[tuple[str, str]]:
    """Pair each quotation with the nearest page citation in `prose`.

    A quotation with no page citation anywhere in the prose is dropped: there
    is no anchor to check it against, so it cannot become a claim.
    """
    anchors = [(m.start(), m.group(1)) for m in _PAGE_ANCHOR.finditer(prose)]
    if not anchors:
        return []

    out = []
    for start, end, text in quoted_spans(prose):
        i = _nearest(anchors, start, end)
        out.append((text, anchors[i][1]))
    return out


def bare_page_anchors(prose: str) -> list[str]:
    """Page citations that no quotation was attributed to.

    These are pointers the prose gives without quoting anything, so there is
    nothing to check them against and they must surface as unverified rather
    than vanish.
    """
    anchors = [(m.start(), m.group(1)) for m in _PAGE_ANCHOR.finditer(prose)]
    if not anchors:
        return []
    claimed = {_nearest(anchors, s, e) for s, e, _ in quoted_spans(prose)}
    return [a for i, (_, a) in enumerate(anchors) if i not in claimed]
