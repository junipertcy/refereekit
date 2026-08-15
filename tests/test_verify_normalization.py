"""A verbatim quotation must verify despite how the PDF encoded it.

Extraction is lossy in typography, not in content: PyMuPDF hands back the fi
ligature, en and em dashes, a Unicode minus, curly quotes, and words broken
across a line with a hyphen. The real fixture contains 51 fi ligatures, 50
dashes of three kinds, and 128 line-break hyphenations. A referee who copies a
sentence out of the rendered PDF, or retypes it correctly, gets none of that --
so `verify` reported a true quotation as FAIL, which is the tool saying a
correct citation is fabricated.

The fix is normalization, not fuzzy matching. Every rule here maps typographic
variants of the same characters onto one form; none of them widens what counts
as a match. An edit-distance or similarity threshold would let a genuine
misquotation PASS, which is the one thing this tool exists to prevent -- hence
the negative tests below, which matter more than the positive ones.
"""
from refereekit.types import Claim, Document, Page
from refereekit.verify import verify


def _doc(text: str, n: int = 1) -> Document:
    return Document(pages=[Page(n=n, text=text)])


def _status(page_text: str, typed: str) -> str:
    return verify(Claim(typed, "quote", "1"), _doc(page_text)).status


# --- typographic variants of identical text ---------------------------------

def test_ligature_matches_its_spelled_out_form():
    """The fixture has 51 of these; 'significant' never matched 'signiﬁcant'."""
    assert _status("a ﬁnite set of nodes", "a finite set of nodes") == "PASS"


def test_en_dash_matches_a_typed_hyphen():
    """A referee types 5-8%; the paper renders 5–8%."""
    assert _status("an error of 5–8% in the tail",
                   "an error of 5-8% in the tail") == "PASS"


def test_unicode_minus_matches_a_typed_hyphen():
    assert _status("a shift of −0.5 in the mean",
                   "a shift of -0.5 in the mean") == "PASS"


def test_curly_quotes_match_straight_ones():
    assert _status("the “effective” theory of learning",
                   'the "effective" theory of learning') == "PASS"


def test_curly_apostrophe_matches_a_straight_one():
    assert _status("the model’s predictive variance is",
                   "the model's predictive variance is") == "PASS"


def test_non_breaking_space_matches_an_ordinary_one():
    assert _status("a total of 12 000 samples drawn",
                   "a total of 12 000 samples drawn") == "PASS"


# --- words broken across a line ---------------------------------------------

def test_word_hyphenated_across_a_line_break_matches_the_whole_word():
    """The fixture breaks words 128 times; 'combinatorial' read as 'combina-'."""
    assert _status("a combina-\ntorial description of the graph",
                   "a combinatorial description of the graph") == "PASS"


def test_compound_hyphenated_at_a_line_break_still_matches_with_its_hyphen():
    """'well-known' broken at a line end is genuinely hyphenated, so both the
    joined and the hyphenated reading have to be searched."""
    assert _status("a well-\nknown result for the kernel",
                   "a well-known result for the kernel") == "PASS"


def test_soft_hyphen_is_ignored():
    assert _status("the ap­proximate posterior over weights",
                   "the approximate posterior over weights") == "PASS"


# --- the guarantee: normalization must not become fuzzy matching ------------

def test_a_genuine_misquotation_still_fails():
    assert _status("the posterior concentrates on the mode",
                   "the posterior concentrates on the mean") == "FAIL"


def test_a_dropped_word_still_fails():
    assert _status("the approximate posterior over the weights",
                   "the approximate posterior over weights") == "FAIL"


def test_joining_a_hyphen_does_not_merge_a_numeric_range():
    """Removing hyphens outright would make 58% match a paper's 5-8%.

    Only a hyphen at a line break is an extraction artefact. One inside a line
    is text, and a referee quoting 58% has misread the paper.
    """
    assert _status("an error of 5-8% in the tail",
                   "an error of 58% in the tail") == "FAIL"


def test_a_quotation_from_another_page_still_fails():
    doc = Document(pages=[Page(n=1, text="a ﬁnite set of nodes"),
                          Page(n=2, text="an unrelated sentence entirely")])
    assert verify(Claim("a finite set of nodes", "quote", "2"), doc).status == "FAIL"


# --- diagnostic on failure ---------------------------------------------------

def test_failure_reports_the_nearest_line():
    """A FAIL should say whether the referee mistyped or the words are absent.

    Reporting only 'not found on page 3' leaves the referee to re-read the page
    by eye, which is the work the tool was supposed to do.
    """
    v = verify(Claim("the posterior concentrates on the mode", "quote", "1"),
               _doc("An opening line.\n"
                    "the posterior concentrates on the mean\n"
                    "A closing line."))
    assert v.status == "FAIL"
    assert "not found on page 1" in v.evidence
    assert "concentrates on the mean" in v.evidence


def test_nearest_line_is_omitted_when_nothing_is_close():
    """A hint that resembles nothing is noise; say only that it is absent."""
    v = verify(Claim("entirely unrelated wording here", "quote", "1"),
               _doc("Bananas. Helicopters. Tuesday."))
    assert v.status == "FAIL"
    assert "not found on page 1" in v.evidence
