import pytest
from refereekit.session import Session, ProvenanceError


def test_ours_and_theirs_are_separate_dirs(tmp_path):
    s = Session.create(tmp_path, "review")
    assert s.ours_dir.name == "ours"
    assert s.theirs_dir.name == "theirs"
    assert s.ours_dir != s.theirs_dir


def test_our_draft_lands_under_ours(tmp_path):
    s = Session.create(tmp_path, "review")
    p = s.our_draft("report.txt")
    p.write_text("our draft")
    assert p.parent.name == "ours"
    assert (s.dir / "ours" / "report.txt").read_text() == "our draft"


def test_put_theirs_lands_under_theirs(tmp_path):
    s = Session.create(tmp_path, "review")
    p = s.put_theirs("referee-2.txt", "their report")
    assert p.parent.name == "theirs"
    assert p.read_text() == "their report"


def test_theirs_is_write_once(tmp_path):
    """A co-referee's report is a received artifact. Silently overwriting it
    is how a genuine quotation got retracted as unverified."""
    s = Session.create(tmp_path, "review")
    s.put_theirs("referee-2.txt", "original")
    with pytest.raises(ProvenanceError):
        s.put_theirs("referee-2.txt", "clobbered")
    assert (s.dir / "theirs" / "referee-2.txt").read_text() == "original"


def test_nothing_resolves_to_the_session_root(tmp_path):
    """A bare report.txt at the root is ambiguous by design."""
    s = Session.create(tmp_path, "review")
    assert s.our_draft("report.txt") != s.dir / "report.txt"
