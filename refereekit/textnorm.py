"""Fold the typography a PDF adds, so comparisons see content not encoding.

Extraction is lossy in typography and faithful in content. PyMuPDF returns the
fi ligature, dashes of several widths, a Unicode minus, curly quotation marks,
soft hyphens, and words the typesetter broke across a line. A referee who copies
a sentence out of the rendered page, or retypes it correctly, produces none of
those.

Comparing raw codepoints therefore fails in both directions, and this module
exists because both failures are the same bug:

  verify  compared a referee's quotation against the page and reported a true
          citation as FAIL -- the tool calling a correct quotation fabricated.

  guard   compared a referee's note against the manuscript and let verbatim
          manuscript text through into a store that outlives the review.

Every rule here maps two spellings of the same characters onto one. None widens
what counts as a match: that distinction is what keeps `verify` a verification
tool rather than a similarity score, and what keeps `guard` closed.
"""
import re
import unicodedata

# Every dash a PDF may carry, mapped to the hyphen a referee types. The Unicode
# minus (U+2212) is included: it is what a typeset "-0.5" actually contains.
_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")

# Curly quotation marks, and the soft hyphen, which renders as nothing and so is
# never in what the referee copied.
_MARKS = {
    ord("“"): '"', ord("”"): '"',
    ord("‘"): "'", ord("’"): "'",
    ord("­"): None,
}

# A hyphen immediately before a line break is where the typesetter broke a word,
# not part of the word.
_LINEBREAK_HYPHEN = re.compile(r"-[ \t]*\n[ \t]*")


def fold(s: str) -> str:
    """Map typographic variants onto one spelling, preserving layout.

    NFKC is what turns the fi ligature into two letters, along with the other
    compatibility forms a PDF hands back. It also flattens superscripts, so "x2"
    and a typeset "x²" fold together -- accepted, because both sides are folded
    alike and the alternative is failing on every word containing "fi".

    Whitespace and case are left alone: callers tokenize differently, and doing
    it here would force one choice on all of them.
    """
    return unicodedata.normalize("NFKC", s).translate(_DASHES).translate(_MARKS)


def collapse(s: str) -> str:
    """Fold typography, then whitespace and case."""
    return re.sub(r"\s+", " ", fold(s)).strip().lower()


def line_break_readings(text: str) -> list[str]:
    """Both readings of text in which a word was broken across a line.

    "combina-\\ntorial" is one word the typesetter split; "well-\\nknown" is a
    hyphenated compound that happened to break at its hyphen. Nothing in the
    text distinguishes them, so both readings are produced and callers search
    both. Neither is a guess about meaning -- each is a spelling the page
    genuinely has, so matching either is still an exact match.

    Only a hyphen at a line break is treated this way. A hyphen inside a line is
    content: dropping those would make a quotation of "58%" match a paper's
    "5-8%", and would let a note saying "58%" past the leak guard.
    """
    return [_LINEBREAK_HYPHEN.sub("", text), _LINEBREAK_HYPHEN.sub("-", text)]
