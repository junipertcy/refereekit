"""Which venues forbid sending the manuscript to an outside LLM.

Zero-retention terms are not a blanket permission. Some venues prohibit sending
a submission to any model other than one they host themselves, and that rule is
independent of how well the transport behaves. Until now it lived in a comment
and the control was "remember not to set REFEREEKIT_ZERO_RETENTION" — which
fails the moment a shell that reviewed a journal paper is reused for a
conference assignment.

The default is *permit*. Refusing every venue the table does not recognise would
make the tool unusable for the long tail of journals, and would be false
precision: code cannot know a venue's policy, and the design has always placed
that judgement with the referee. What the table can do is make the prohibitions
the referee already knows about impossible to forget.

`REFEREEKIT_VENUE_POLICY` points at a TOML file that extends or overrides the
built-in table, because policy is the referee's to state and it changes without
this package being released:

    [venues]
    NeurIPS = { llm = false }
    "Some Journal" = { llm = false }
"""
import os
import re
import tomllib
from pathlib import Path

# Venues known to prohibit sending submissions to an outside model. Keys are
# matched against a normalized venue string, so "NeurIPS" catches both the bare
# name and an OpenReview id such as "NeurIPS.cc/2026/Conference".
_BUILTIN: dict[str, bool] = {
    "neurips": False,
}


class VenuePolicyError(ValueError):
    """Raised when a venue forbids the LLM path the command would take.

    A ValueError, like ManuscriptLeakError, so that every command's existing
    handler reports it as a clean error. Requiring each call site to add it to
    an except tuple is how or-responses shipped ungated: the gate was there and
    the refusal escaped as a traceback.
    """


def _normalize(venue: str) -> str:
    """Lowercase and strip separators so ids and bare names compare equal."""
    return re.sub(r"[^a-z0-9]+", "", venue.lower())


def _table() -> dict[str, bool]:
    table = dict(_BUILTIN)
    override = os.environ.get("REFEREEKIT_VENUE_POLICY")
    if not override:
        return table
    raw = tomllib.loads(Path(override).read_text())
    for name, entry in (raw.get("venues") or {}).items():
        if isinstance(entry, dict) and "llm" in entry:
            table[_normalize(name)] = bool(entry["llm"])
    return table


def llm_permitted(venue: str | None) -> bool:
    """True unless the venue is listed as prohibiting an outside LLM."""
    if not venue:
        return True
    norm = _normalize(venue)
    for key, permitted in _table().items():
        if key and key in norm:
            return permitted
    return True


def assert_llm_permitted(venue: str | None) -> None:
    if llm_permitted(venue):
        return
    raise VenuePolicyError(
        f"{venue} prohibits sending the submission to an outside model, so this "
        f"command will not send it. Use the venue's own review interface. If "
        f"this rule has changed, override it with a REFEREEKIT_VENUE_POLICY "
        f"file containing:  [venues]\n    \"{venue}\" = {{ llm = true }}"
    )
