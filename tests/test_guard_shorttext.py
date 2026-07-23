import pytest
import re
from refereekit.guard import assert_no_manuscript, is_verbatim_fragment, ManuscriptLeakError

def test_short_verbatim_fragment_detected(real_doc):
    # a short (<8-word) phrase copied verbatim from page 1
    assert is_verbatim_fragment("prescribed degree-size sequences", real_doc) is True

def test_short_authored_note_not_flagged(real_doc):
    assert is_verbatim_fragment("PRX: lean accept-after-major", real_doc) is False

def test_assert_rejects_short_verbatim(real_doc):
    with pytest.raises(ManuscriptLeakError):
        assert_no_manuscript("prescribed degree-size sequences", real_doc)

def test_assert_allows_short_authored_note(real_doc):
    assert_no_manuscript("PRX: terse; reserve imperatives for real flaws", real_doc)

def test_long_note_with_embedded_verbatim_fragment_flagged(real_doc):
    # Extract an 8-word verbatim run from page 1 programmatically
    page1_text = real_doc.pages[0].text
    words = re.findall(r"\w+", page1_text.lower())
    # Take 8 consecutive words from position 10 (skip title/header noise)
    verbatim_fragment_words = words[10:18]
    verbatim_fragment = " ".join(verbatim_fragment_words)

    # Embed it in a longer note (>= 8 words total)
    long_note = f"In my view, {verbatim_fragment} is the core claim here, and it merits publication."

    # The long note should be flagged because it contains a verbatim 8-word run
    assert is_verbatim_fragment(long_note, real_doc, n=8) is True
    with pytest.raises(ManuscriptLeakError):
        assert_no_manuscript(long_note, real_doc, n=8)

def test_long_authored_note_still_passes(real_doc):
    # A long note that is not from the manuscript
    long_note = "PRX: lean accept-after-major on approximate-but-validated theory work here"
    assert is_verbatim_fragment(long_note, real_doc) is False
    assert_no_manuscript(long_note, real_doc)
