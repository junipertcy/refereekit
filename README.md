# refereekit

Standalone, harness-portable toolkit that automates a paper-review workflow.
Phase 1 (this release): ingest a PDF, verify factual anchors against it, guard
manuscript text from leaving the machine, and serve a live Q&A page.

## Confidentiality
Confidential manuscripts and text derived from them are never committed. The only
committable PDF is the test fixture under `tests/fixtures/`. Manuscript text is
never sent to any network service in Phase 1 (no LLM/Exa/memory yet).

## Install
    python -m venv .venv && .venv/bin/pip install -e ".[dev]"

## Use
    refereekit ingest paper.pdf --session ./work/paperA
    refereekit verify --session ./work/paperA --kind quote --anchor 16 --text "5-8%"
    refereekit serve  --session ./work/paperA --port 8888

## Test
    .venv/bin/pytest -v
