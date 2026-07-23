import pytest
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
