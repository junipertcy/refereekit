# refereekit — working rules

A standalone Python CLI that automates a peer-review workflow: ingest a
submitted PDF, verify every factual anchor against it, and draft a referee
report and editor letter in the referee's voice. No agent harness is required
to run it; `refereekit review <pdf>` drives the whole pipeline itself.

## Confidentiality comes first

Manuscripts under review are confidential. These are hard rules, not defaults:

- **Never commit manuscript text, or anything derived from it.** Not PDFs, not
  extracted text, not drafts, not quotes in a commit message.
- **Never paste manuscript text into a chat, a web search, or any tool other
  than the zero-retention LLM backend.** That includes asking me to "look at"
  a paper by pasting it.
- **`work/` is per-review scratch and is git-ignored. Never `git add -f` it.**
- The only committable PDFs are the two test fixtures in `tests/fixtures/`.
- `style/STYLE.md` is a distilled voice guide and *is* committable. Raw reports
  are not.

**Read before staging anything:** `.gitignore` denies manuscript files at
every depth and allows this repository's own by name (`tests/test_gitignore.py`
pins both halves), but it protects only `*.pdf`, `index.html` and `work/`; a
session's `doc.json`, `state.json`, `ours/` and `theirs/` anywhere else are
committable. Keep sessions under `work/`. Never `git add -A` or `git add .` in
this repo. Stage named paths, and run `git status` before every commit.

`.env` holds a real OpenReview password. Never read it back into the
conversation, print it, or copy values out of it. `.env.template` carries names
and no values and is the only one committed.

## Build and test

    python -m venv .venv && .venv/bin/pip install -e ".[dev,llm]"
    .venv/bin/pytest                      # whole suite
    .venv/bin/pytest tests/test_guard.py  # one file

Tests run fully offline. Never add a test that needs a network call or a real
API key; use `REFEREEKIT_FAKE=1` or the `FakeBackend`.

## Invariants that must not regress

These encode the safety model. Changing one is a design decision, not a
refactor — raise it before touching it.

- **`llm.complete()` refuses any backend not marked `zero_retention`**
  (`refereekit/llm.py`). Manuscript text reaches a model only through it.
- **`guard.assert_no_manuscript()` fails closed** — an empty or unreadable
  document is a rejection, not a pass (`refereekit/guard.py`). Memory writes
  and literature searches go through it.
- **`ours/` and `theirs/` are separate and `theirs/` is write-once**
  (`refereekit/session.py`). A co-referee's report is evidence; our draft is
  not. Do not collapse them or write a loose `report.txt` into the session root.
- **Memory never stores manuscript text.** Notes are referee-authored only —
  no LLM auto-distillation, no extraction from the paper.
- Anchor verification is `PASS` / `FAIL` / `FLAG`. A `FLAG` still enters the
  claim pool (the page exists, only the wording is unchecked); a `FAIL` does not.

## Conventions

- Python 3.11+, stdlib-first. Runtime dependency is PyMuPDF; `anthropic` and
  `openreview-py` are optional extras, imported lazily so the package imports
  without them.
- Every module is a plain Python API *and* a CLI subcommand; `cli.py` is a thin
  wrapper. Put logic in the module, never in `cli.py`.
- Comments explain *why*, not *what* — match the density already in the file.
- Design specs and plans live in `docs/superpowers/`. Read the relevant spec
  before changing a subsystem.
