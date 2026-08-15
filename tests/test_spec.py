"""A review spec is the referee's side of a review, written down before the run.

The gates in `run_review` were built for typed answers. A real verdict is a
considered piece of prose drafted over days, which is a file, not something you
type at a prompt. The spec carries those answers as named fields so the ordering
the gates expect lives in one tested place instead of in a hand-built list.
"""
import pytest

from refereekit.spec import ReviewSpec, SpecError, load_spec, scripted_input

MINIMAL = """
questions = ["Where does the derivation stop being exact?"]

[verdict]
recommend = "Publish after major revision."
venue = "PRX"
major_minor = "major"
"""


def _write(tmp_path, text, name="review.toml"):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_load_reads_questions_and_verdict(tmp_path):
    spec = load_spec(_write(tmp_path, MINIMAL))
    assert isinstance(spec, ReviewSpec)
    assert spec.questions == ["Where does the derivation stop being exact?"]
    assert spec.verdict["venue"] == "PRX"


def test_multiline_prose_survives_the_round_trip(tmp_path):
    """The whole point of TOML here is that a long verdict stays readable."""
    spec = load_spec(_write(tmp_path, '''
questions = ["q"]

[verdict]
recommend = """
MAJOR ISSUE 1: the Ansatz is uncontrolled.
MAJOR ISSUE 2: the validation is mismatched.
"""
venue = "PRX"
major_minor = "major"
'''))
    assert "MAJOR ISSUE 1" in spec.verdict["recommend"]
    assert "MAJOR ISSUE 2" in spec.verdict["recommend"]


def test_optional_sections_default_to_empty(tmp_path):
    spec = load_spec(_write(tmp_path, MINIMAL))
    assert spec.section_lengths == {}
    assert spec.editor_answers == {}


def test_missing_verdict_is_refused(tmp_path):
    """Fail closed: a spec without a verdict would silently draft an empty one."""
    with pytest.raises(SpecError, match="verdict"):
        load_spec(_write(tmp_path, 'questions = ["q"]\n'))


def test_verdict_missing_a_required_key_is_refused(tmp_path):
    with pytest.raises(SpecError, match="major_minor"):
        load_spec(_write(tmp_path, '''
questions = ["q"]

[verdict]
recommend = "r"
venue = "PRX"
'''))


def test_empty_questions_is_refused(tmp_path):
    """A review with no questions asked has an empty claim pool to draft from."""
    with pytest.raises(SpecError, match="questions"):
        load_spec(_write(tmp_path, '''
questions = []

[verdict]
recommend = "r"
venue = "PRX"
major_minor = "major"
'''))


def test_scripted_input_feeds_the_gates_in_order(tmp_path):
    """The sequence must match what run_review's gates consume, in order.

    Q&A questions, then a blank to close the loop, then recommend / venue /
    major-minor, then section lengths, then editor key-answer pairs, then a
    blank to close the editor loop.
    """
    spec = load_spec(_write(tmp_path, '''
questions = ["q1", "q2"]

[verdict]
recommend = "r"
venue = "PRX"
major_minor = "major"

[section_lengths]
intro = "short"

[editor_answers]
a = "yes"
'''))
    fn = scripted_input(spec)
    assert [fn("") for _ in range(9)] == [
        "q1", "q2", "",          # Q&A loop, blank closes it
        "r", "PRX", "major",     # verdict gate
        "intro=short",           # detail gate
        "a", "yes",              # editor answers
    ]
    assert fn("") == ""          # blank closes the editor loop


def test_scripted_input_is_exhausted_safely(tmp_path):
    """Past the end it returns blank, so a gate can never block on empty input."""
    spec = load_spec(_write(tmp_path, MINIMAL))
    fn = scripted_input(spec)
    for _ in range(20):
        fn("")
    assert fn("") == ""
