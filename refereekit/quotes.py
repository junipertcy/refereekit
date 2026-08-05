"""Find the quotations in generated prose and pair them with page citations.

Only text the author presented as a quotation is a candidate for substring
verification. Referee prose paraphrases the manuscript; it does not reproduce
it. Verifying a whole sentence against the page would fail on every honest
paraphrase, so this module narrows verification to quoted spans.
"""
import re

# Straight or curly quotes around at least 12 characters. The floor keeps out
# scare-quoted jargon ("not innocuous") that carries no page-checkable content.
_QUOTED = re.compile(r'[""]([^""]{12,400})[""]')

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
        if not text:
            continue
        start = m.start(1) + lead
        out.append((start, start + len(text), text))
    return out


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
        # Distance from the quotation to each anchor; 0 if the anchor sits
        # inside the quoted span (a quote that cites itself).
        nearest = min(anchors, key=lambda a: 0 if start <= a[0] <= end
                      else min(abs(a[0] - end), abs(start - a[0])))
        out.append((text, nearest[1]))
    return out
