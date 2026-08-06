import pytest

from refereekit.llm import FakeBackend, RetentionError
from refereekit.openreview import responses


def test_prompt_carries_our_review_and_what_we_received():
    p = responses.build_prompt("we asked about Eq. (3)", ["the authors replied"])
    assert "we asked about Eq. (3)" in p
    assert "the authors replied" in p


def test_prompt_forbids_recommending_a_score():
    """The output is a reading aid. A rating is the referee's to decide."""
    p = responses.build_prompt("ours", ["theirs"])
    assert "Do not recommend a rating" in p


def test_prompt_asks_for_the_three_buckets():
    p = responses.build_prompt("ours", ["theirs"])
    for want in ("does not address", "should re-check"):
        assert want in p


def test_prompt_ends_with_the_stale_document_warning():
    """doc.json holds the version originally fetched, so a claim about a
    revised manuscript cannot be verified against it."""
    p = responses.build_prompt("ours", ["theirs"])
    assert p.rstrip().endswith(
        "doc.json, which holds the version originally fetched.")


def test_multiple_received_notes_are_separated():
    p = responses.build_prompt("ours", ["first note", "second note"])
    assert "first note" in p and "second note" in p
    assert p.index("first note") < p.index("second note")


def test_no_draft_yet_is_stated_not_left_blank():
    """Reading the responses before drafting is a legitimate order of work."""
    p = responses.build_prompt("   ", ["theirs"])
    assert "we have not drafted our review yet" in p


def test_analyze_returns_the_backend_text():
    assert responses.analyze("ours", ["theirs"],
                             backend=FakeBackend("analysis")) == "analysis"


def test_analyze_with_nothing_received_is_an_error():
    """An empty output file would read as 'the authors said nothing'."""
    with pytest.raises(ValueError, match="nothing to analyze"):
        responses.analyze("ours", [], backend=FakeBackend("x"))


def test_analyze_refuses_a_backend_that_is_not_zero_retention():
    """Author responses are manuscript-adjacent text."""
    with pytest.raises(RetentionError):
        responses.analyze("ours", ["theirs"],
                          backend=FakeBackend("x", zero_retention=False))
