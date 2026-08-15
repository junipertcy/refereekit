"""No command may reach a model when the session's venue forbids it.

This is deliberately not a list of gated commands. A list is the same artefact
that let `or-responses` ship ungated while four sibling commands were gated: the
list and the code drift, and nothing notices. Instead the CLI's own subparsers
are enumerated, so a command added later is covered the moment it exists.

The mechanism is a poisoned backend. `_backend()` is replaced with a factory
that raises on construction, so "reached a model" becomes a test failure rather
than a network call. A command passes if it either refuses or never asks for a
backend; it fails if it constructs one for a session whose venue prohibits
outside models.
"""
import contextlib
import io
import re
from pathlib import Path

import pytest

from refereekit import cli as climod
from refereekit.cli import main
from refereekit.session import Session

PROHIBITED = "NeurIPS.cc/2026/Conference"


class ReachedTheModel(AssertionError):
    """Raised in place of building a backend, so the failure names itself."""


def _subcommands() -> list[str]:
    """Every subcommand the CLI exposes, read from its own --help.

    Reading the command surface rather than restating it is the whole point: a
    subcommand added later appears here without anyone remembering to add it.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        with contextlib.suppress(SystemExit):
            main(["--help"])
    m = re.search(r"\{([a-z0-9,\-]+)\}", buf.getvalue())
    assert m, "could not read the subcommand list from --help"
    return m.group(1).split(",")


# The minimal invocation for each subcommand. Argument shapes differ per
# command, so each needs its own; that is the cost of discovering commands
# instead of listing gated ones, and it is still cheaper than a list, because a
# new command shows up here as a KeyError rather than as silence.
def _invocation(name: str, session) -> list[str] | None:
    """Args for `name`, or None if it cannot reach a model at all."""
    session = Path(session)
    s = str(session)
    return {
        "draft": ["draft", "--session", s],
        "editor": ["editor", "--session", s, "--answers", "a=yes"],
        "review": ["review", str(session / "paper.pdf"), "--session", s],
        "or-draft": ["or-draft", "--session", s],
        "or-responses": ["or-responses", "--session", s],
        # Reach no model: local inspection, fetching, or serving.
        "ingest": None,
        "verify": None,
        "serve": None,
        "mem-store": None,
        "mem-recall": None,
        "or-fetch": None,
    }[name]


@pytest.fixture
def prohibited_session(tmp_path, real_pdf_path):
    """A session recorded against a venue that forbids outside models."""
    from refereekit.ingest import ingest
    from refereekit.types import Claim

    s = Session.create(tmp_path, "s")
    s.save_doc(ingest(real_pdf_path))
    s.record_claim(Claim("counting identity", "equation", "1"))
    s.set_state("venue", PROHIBITED)
    s.set_state("verdict", {"recommend": "minor", "venue": PROHIBITED})
    (s.dir / "paper.pdf").write_bytes(real_pdf_path.read_bytes())
    (s.dir / "theirs").mkdir(exist_ok=True)
    (s.dir / "theirs" / "r1.txt").write_text("A response about the paper.")
    (s.dir / "form.json").write_text(
        '{"invitation_id": "x", "fields": [{"name": "summary", "type": "string"}]}')
    return s.dir


def test_every_subcommand_is_covered_by_this_test():
    """A new subcommand must be classified here, not silently skipped."""
    for name in _subcommands():
        _invocation(name, "/tmp/x")   # KeyError if unclassified


@pytest.mark.parametrize("name", [
    n for n in _subcommands() if _invocation(n, "/tmp/x") is not None])
def test_a_prohibited_venue_stops_the_command(name, prohibited_session,
                                              monkeypatch, capsys):
    monkeypatch.setenv("REFEREEKIT_ZERO_RETENTION", "1")
    monkeypatch.delenv("REFEREEKIT_FAKE", raising=False)

    def poisoned():
        raise ReachedTheModel(
            f"{name} built a backend for a venue that prohibits outside models")

    monkeypatch.setattr(climod, "_backend", poisoned)
    rc = main(_invocation(name, prohibited_session))
    assert rc == 2, f"{name} did not refuse"
    assert "prohibits" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("name", [
    n for n in _subcommands() if _invocation(n, "/tmp/x") is None])
def test_a_command_that_reaches_no_model_is_not_blocked(name):
    """The gate must not over-reach.

    A venue that forbids outside models forbids sending the submission, not
    reading it. Ingesting, verifying an anchor locally, serving the rendered
    page and fetching from OpenReview must all still work on such a session --
    which is most of the value refereekit offers for those venues.
    """
    assert _invocation(name, "/tmp/x") is None


def test_a_local_verify_still_works_on_a_prohibited_session(prohibited_session,
                                                            capsys):
    """The concrete case: anchor verification is the whole product for a venue
    where nothing may be sent to a model."""
    rc = main(["verify", "--session", str(prohibited_session),
               "--kind", "equation", "--anchor", "1", "--text", "counting"])
    assert rc == 0
    assert "PASS" in capsys.readouterr().out
