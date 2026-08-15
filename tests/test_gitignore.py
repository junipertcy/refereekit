"""The ignore rules are a confidentiality control, so they are tested like one.

A manuscript under review must not be committable. The rules were anchored to
the repository root, which protected the test fixtures by accident of position:
anything one directory down -- `docs/`, a session directory pointed at by
`--session`, a scratch folder -- was committable by `git add -A`.

Root-anchoring is default-allow with a narrow deny. These tests pin the inverse:
every PDF and every manuscript-derived text file is denied wherever it sits, and
the handful of repository files that share those shapes are allowed by name. An
allow-list of three is auditable; a deny-list of "wherever a manuscript might
land" cannot be.
"""
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    not (REPO / ".git").exists(), reason="not a git checkout")


def _ignored(path: str) -> bool:
    """Whether git would refuse to add `path`. Pure pattern matching; the file
    need not exist, which is what lets this test name a manuscript without
    creating one."""
    return subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", path],
        cwd=REPO).returncode == 0


# --- manuscripts, wherever they land ----------------------------------------

def test_a_manuscript_pdf_at_the_root_is_ignored():
    assert _ignored("MANUSCRIPT.pdf")


def test_a_manuscript_pdf_in_a_subdirectory_is_ignored():
    """The hole: `git add -A` would have committed this."""
    assert _ignored("docs/MANUSCRIPT.pdf")


def test_a_manuscript_pdf_in_a_nested_session_is_ignored():
    assert _ignored("reviews/2026/prx/paper.pdf")


def test_derived_text_in_a_subdirectory_is_ignored():
    assert _ignored("scratch/MANUSCRIPT_raw.txt")
    assert _ignored("scratch/MANUSCRIPT_plain.txt")
    assert _ignored("notes/review_draft_MANUSCRIPT.txt")
    assert _ignored("notes/editor_response_MANUSCRIPT.txt")


def test_a_rendered_session_page_outside_work_is_ignored():
    """--session takes any path, so a session need not be under work/."""
    assert _ignored("reviews/prx-42/index.html")


def test_the_per_review_working_directory_is_ignored():
    assert _ignored("work/MANUSCRIPT-review/ours/report.txt")


# --- the repository's own files must stay committable ------------------------

def test_the_test_fixtures_are_not_ignored():
    """Named exceptions. Without these the suite's own inputs vanish."""
    assert not _ignored("tests/fixtures/real_paper.pdf")
    assert not _ignored("tests/fixtures/sample_paper.pdf")


def test_the_diagrams_page_is_not_ignored():
    """Repository documentation that happens to share a session file's name."""
    assert not _ignored("diagrams/index.html")


def test_ordinary_source_and_docs_are_not_ignored():
    assert not _ignored("refereekit/verify.py")
    assert not _ignored("README.md")
    assert not _ignored("docs/review-spec.example.toml")
