"""Load a review spec: the referee's answers, written down before the run.

`run_review` drives its gates through `input_fn`, which was built for a person
typing at a prompt. The answers that matter in a real review — the questions to
put to the manuscript, the verdict, the editor replies — are long, considered
prose that belongs in a file under version control, not in a terminal.

A spec is TOML because `tomllib` is in the standard library from 3.11 and TOML
has multi-line strings. JSON would force a thousand-word verdict onto one
escaped line, and YAML would be a dependency this package does not otherwise
need.

The order the gates consume input in is knowledge that lived in the referee's
hand-built list, where a miscount shifted every later answer by one without
saying so. `scripted_input` is the one place that knows it.
"""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

_VERDICT_KEYS = ("recommend", "venue", "major_minor")


class SpecError(ValueError):
    """Raised when a spec cannot be used as written."""


@dataclass
class ReviewSpec:
    questions: list[str]
    verdict: dict[str, str]
    section_lengths: dict[str, str] = field(default_factory=dict)
    editor_answers: dict[str, str] = field(default_factory=dict)
    venue: str | None = None


def load_spec(path) -> ReviewSpec:
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise SpecError(f"{path}: not valid TOML: {e}") from e

    questions = raw.get("questions") or []
    if not questions:
        raise SpecError(
            f"{path}: 'questions' is empty; a review that asks nothing leaves an "
            "empty claim pool and the draft would have nothing verified to cite"
        )

    verdict = raw.get("verdict")
    if not verdict:
        raise SpecError(f"{path}: no 'verdict' table")
    missing = [k for k in _VERDICT_KEYS if not verdict.get(k)]
    if missing:
        raise SpecError(f"{path}: verdict is missing {', '.join(missing)}")

    return ReviewSpec(
        questions=list(questions),
        verdict={k: str(verdict[k]).strip() for k in _VERDICT_KEYS},
        section_lengths=dict(raw.get("section_lengths") or {}),
        editor_answers=dict(raw.get("editor_answers") or {}),
        venue=raw.get("venue") or verdict.get("venue"),
    )


def scripted_input(spec: ReviewSpec) -> Callable[[str], str]:
    """Build an `input_fn` that feeds `run_review`'s gates from the spec.

    Past the end it returns blank rather than raising: every gate treats blank
    as "done", so an exhausted script closes its loops instead of blocking.
    """
    seq: list[str] = list(spec.questions)
    seq.append("")                                  # closes the Q&A loop
    seq += [spec.verdict[k] for k in _VERDICT_KEYS]
    seq.append(",".join(f"{k}={v}" for k, v in spec.section_lengths.items()))
    for key, answer in spec.editor_answers.items():
        seq += [key, answer]
    seq.append("")                                  # closes the editor loop

    feed = iter(seq)

    def input_fn(prompt: str) -> str:
        return next(feed, "")

    return input_fn
