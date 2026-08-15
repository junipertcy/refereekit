"""The leak guard must fold typography the same way `verify` does.

One missing normalization produced two opposite failures. In `verify` it made a
true quotation FAIL, because the referee typed "finite" where the PDF held the
fi ligature. Here it does the reverse and worse: the same fragment is verbatim
manuscript text, and the guard let it through into a store that outlives the
review. A fail-closed design that compares raw codepoints is only closed against
the spellings it happens to have seen.
"""
import pytest

from refereekit.guard import ManuscriptLeakError, assert_no_manuscript
from refereekit.types import Document, Page


def _doc(text: str) -> Document:
    return Document(pages=[Page(n=1, text=text)])


def _blocked(page_text: str, note: str) -> bool:
    try:
        assert_no_manuscript(note, _doc(page_text))
        return False
    except ManuscriptLeakError:
        return True


def test_a_short_fragment_retyped_without_the_ligature_is_blocked():
    """Under the eight-word floor this takes the exact-substring path, where the
    n-gram net that incidentally catches longer passages does not apply."""
    assert _blocked("a ﬁnite set of nodes", "finite set of nodes")


def test_a_fragment_retyped_with_a_plain_hyphen_is_blocked():
    assert _blocked("an error of 5–8% here", "error of 5-8% here")


def test_a_fragment_retyped_with_a_straight_apostrophe_is_blocked():
    assert _blocked("the model’s variance grows", "model's variance grows")


def test_a_word_the_typesetter_broke_is_blocked_when_written_whole():
    assert _blocked("a combina-\ntorial description", "combinatorial description")


def test_referee_prose_that_is_not_in_the_paper_is_still_allowed():
    """The guard must stay usable: folding typography must not start rejecting
    notes the referee wrote themselves."""
    assert not _blocked("a ﬁnite set of nodes",
                        "PRX: lean accept-after-major on approximate theory")
