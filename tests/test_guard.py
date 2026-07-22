import pytest
from refereekit.guard import assert_no_manuscript, ManuscriptLeakError

def test_topic_query_passes(sample_doc):
    assert_no_manuscript("simplicial complexes degree sequences realizability", sample_doc)

def test_manuscript_sentence_is_rejected(sample_doc):
    leak = sample_doc.page_text(1)[:200]  # a real chunk of the paper
    with pytest.raises(ManuscriptLeakError):
        assert_no_manuscript(leak, sample_doc)
