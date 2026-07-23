from refereekit.agent.loop import _doc_context
from refereekit.types import Document, Page

def _doc():
    return Document(pages=[Page(1, "alpha beta gamma", []), Page(2, "delta epsilon", [])],
                    figures=[], equations=[], sections=[])

def test_context_includes_doc_transcript_and_question():
    ctx = _doc_context(_doc(), [("prior q", "prior a")], "new question?")
    assert "alpha beta" in ctx           # doc content present
    assert "prior q" in ctx and "prior a" in ctx   # transcript present
    assert "new question?" in ctx        # current question present

def test_context_empty_transcript_ok():
    ctx = _doc_context(_doc(), [], "q1")
    assert "q1" in ctx and "alpha" in ctx
