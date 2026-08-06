from refereekit import drafts
from refereekit.llm import FakeBackend
from refereekit.session import Session
from refereekit.ingest import ingest

POOL = {"claims": [], "verdict": {"recommend": "minor"}}


def test_field_instruction_appears_in_the_prompt():
    p = drafts.build_prompt(POOL, "voice", {}, None,
                            field_instruction="Write the 'summary' field.")
    assert "=== THIS SECTION ===" in p
    assert "Write the 'summary' field." in p


def test_field_instruction_precedes_section_lengths():
    """Order matters for readability of the assembled prompt."""
    p = drafts.build_prompt(POOL, "voice", {}, None, field_instruction="X")
    assert p.index("=== THIS SECTION ===") < p.index("=== SECTION LENGTHS ===")


def test_omitting_field_instruction_changes_nothing():
    """The existing draft and editor paths must produce identical prompts."""
    without = drafts.build_prompt(POOL, "voice", {"intro": "short"})
    explicit_none = drafts.build_prompt(POOL, "voice", {"intro": "short"},
                                        None, None)
    assert without == explicit_none
    assert "THIS SECTION" not in without


def test_report_passes_field_instruction_through(tmp_path, real_pdf_path):
    """report() is what fill.py calls, so the keyword has to reach the prompt
    from there, not just from build_prompt."""
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(real_pdf_path))
    seen = []
    backend = FakeBackend(lambda prompt: seen.append(prompt) or "drafted")
    d = drafts.report(s, {}, {}, backend=backend, style_path="style/STYLE.md",
                      field_instruction="Write the 'weaknesses' field.")
    assert d.text == "drafted"
    assert "Write the 'weaknesses' field." in seen[0]
