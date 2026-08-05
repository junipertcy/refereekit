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

# Sentence scope decides attribution, so we need sentence ends. A semicolon
# counts: `Page 7 says "..."; page 15 shows the panels.` cites two pages about
# two different things.
_TERMINATOR = re.compile(r"[.!?;](?=\s|$)")

# A period after one of these is an abbreviation, not a sentence end. Without
# this, "on p. 7" would split mid-sentence and the citation would fall outside
# the sentence it belongs to.
_ABBREVIATIONS = {"p", "pp", "eq", "eqs", "fig", "figs", "cf", "sec", "secs",
                  "ref", "refs", "no", "vs", "al", "e.g", "i.e", "resp"}

_WORD_BEFORE = re.compile(r"([A-Za-z.]+)$")


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


def _sentence_breaks(prose: str) -> list[int]:
    """Offsets of sentence terminators, skipping known abbreviations."""
    out = []
    for m in _TERMINATOR.finditer(prose):
        w = _WORD_BEFORE.search(prose[:m.start()])
        if w and w.group(1).lower().rstrip(".") in _ABBREVIATIONS:
            continue
        out.append(m.start())
    return out


def _sentence_of(breaks: list[int], pos: int) -> int:
    """Index of the sentence containing `pos`."""
    return sum(1 for b in breaks if b < pos)


def _pick(anchors, breaks, claimed, start, end) -> int:
    """Index of the page citation this quotation is attributed to.

    A citation inside the quotation is part of the quoted words and wins
    outright. Otherwise the prose's own attribution decides: prefer a citation
    in the same sentence, prefer one not already taken by an earlier quotation,
    and within a pool prefer the nearest one before the quotation, falling back
    to the nearest one after it.

    Sentence scope, not character distance, is the discriminator. A citation in
    a previous sentence attributes nothing to a quotation in this one, however
    few characters separate them. The pools degrade in that order because
    exclusivity is a preference, not a law: three quotations can legitimately
    share one citation.

    This answers only what the prose claims, never which page the words are
    actually on. Re-attributing a quotation to the page where it happens to be
    found would make every citation verify and silently erase the
    misattributions this tool exists to catch.
    """
    for i, (pos, _) in enumerate(anchors):
        if start <= pos <= end:
            return i
    sent = _sentence_of(breaks, start)
    same = [i for i, (pos, _) in enumerate(anchors)
            if _sentence_of(breaks, pos) == sent]
    for pool in ([i for i in same if i not in claimed],
                 same,
                 [i for i in range(len(anchors)) if i not in claimed],
                 list(range(len(anchors)))):
        if not pool:
            continue
        before = [i for i in pool if anchors[i][0] < start]
        if before:
            return max(before, key=lambda i: anchors[i][0])
        after = [i for i in pool if anchors[i][0] > end]
        if after:
            return min(after, key=lambda i: anchors[i][0])
    return 0


def _attribute(prose: str) -> tuple[list[tuple[str, str]], set[int], list[tuple[int, str]]]:
    """Attribute each quotation in `prose` to a page citation.

    Returns (pairs, claimed_indices, anchors). `pair_with_pages` and
    `bare_page_anchors` are two views of this one result, so they cannot
    disagree about which citation a quotation took.

    Quotations are walked in document order because attribution is stateful:
    `claimed` grows as each quotation takes a citation, and an earlier
    quotation's choice constrains a later one's. `quoted_spans` already yields
    document order.
    """
    anchors = [(m.start(), m.group(1)) for m in _PAGE_ANCHOR.finditer(prose)]
    if not anchors:
        return [], set(), anchors
    breaks = _sentence_breaks(prose)
    pairs, claimed = [], set()
    for start, end, text in quoted_spans(prose):
        i = _pick(anchors, breaks, claimed, start, end)
        claimed.add(i)
        pairs.append((text, anchors[i][1]))
    return pairs, claimed, anchors


def pair_with_pages(prose: str) -> list[tuple[str, str]]:
    """Pair each quotation with the page citation the prose attributes it to.

    A quotation with no page citation anywhere in the prose is dropped: there
    is no anchor to check it against, so it cannot become a claim.
    """
    return _attribute(prose)[0]


def bare_page_anchors(prose: str) -> list[str]:
    """Page citations that no quotation was attributed to.

    These are pointers the prose gives without quoting anything, so there is
    nothing to check them against and they must surface as unverified rather
    than vanish.
    """
    _, claimed, anchors = _attribute(prose)
    return [a for i, (_, a) in enumerate(anchors) if i not in claimed]
