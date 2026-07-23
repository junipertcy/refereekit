# refereekit

Standalone, harness-portable toolkit that automates a paper-review workflow.

## Confidentiality
Confidential manuscripts and text derived from them are never committed. The only
committable PDF is the test fixture under `tests/fixtures/`. Manuscript text is
guarded: it only flows to LLM backends explicitly configured with zero-retention.
The distilled `style/STYLE.md` voice guide is committable; raw reports are never
committed or sent to any service.

## Install
    python -m venv .venv && .venv/bin/pip install -e ".[dev]"

## Use

### Phase 1 (SP-A): Ingest, Verify, Serve
    refereekit ingest paper.pdf --session ./work/paperA
    refereekit verify --session ./work/paperA --kind quote --anchor 16 --text "5-8%"
    refereekit serve  --session ./work/paperA --port 8888

### Phase 2 (SP-B): Draft Generation
Generate referee reports and editor letters using a verified claim pool.

**Backend selection (environment variables):**
- **Offline mode (for testing):** Set `REFEREEKIT_FAKE=1` to use a fake backend that
  returns canned text without calling any API. Optionally set `REFEREEKIT_FAKE_TEXT`
  to control the returned text.
- **Real LLM (zero-retention only):** Set `REFEREEKIT_ZERO_RETENTION=1` to confirm
  zero-retention terms. Optionally set `REFEREEKIT_MODEL` (default: `claude-opus-4-8`).
  Requires the `anthropic` package: `pip install -e ".[llm]"`

**Commands:**
    # Generate a referee report
    export REFEREEKIT_ZERO_RETENTION=1
    refereekit draft --session ./work/paperA [--length intro=short ...]

    # Generate an editor response letter
    refereekit editor --session ./work/paperA --answers a=yes --answers b=no

**Output:** Draft text is written to `<session>/drafts/report.txt` or `editor.txt`.
The command prints a summary including flag count. Flags indicate anchors that failed
verification (not in verified pool or failed re-verification against the document).

**Confidentiality note:** Manuscript text flows only through backends configured with
`zero_retention=True`. The `style/STYLE.md` voice guide is distilled and committable;
raw manuscript text and reports are never committed.

### Phase 3 (SP-C): Memory

Store and recall referee-authored notes across sessions. Memory is guarded:
manuscript-verbatim text can never be stored. All notes are explicitly written by the
referee — no LLM auto-distillation, no automatic extraction from manuscripts.

**Guarded write:**
- `mem-store` requires a session document to validate against. If the input text is a
  verbatim fragment from the manuscript (≥8-word n-gram match), the write is rejected
  (exit 2, printed error) and nothing is stored.
- This fail-closed design ensures manuscript confidentiality: text under review cannot
  leak into memory.

**Commands:**
    # Store a referee-authored note (requires --session to guard against manuscript text)
    refereekit mem-store --session ./work/paperA --venue PRX --kind verdict \
        --text "PRX: lean accept-after-major on approximate-but-validated theory" \
        --db ./work/memory.db

    # Recall notes for a venue (default: 20 most recent, deduplicated by normalized text)
    refereekit mem-recall --venue PRX --db ./work/memory.db

**Deduplication and recency:**
- Recall deduplicates by normalized text (case-folded, whitespace-collapsed).
- Returns the most recent note for each unique text, up to 20 notes (configurable).
- Sorted by `created_at` descending.

**Note kinds:** `verdict`, `quote`, `claim`, `method`, `style` — the `kind` field is
stored but not used for filtering in this phase.

## Extraction limits

- **Figures:** Reliably extracted from caption lines (handles "FIG." and "Figure" prefixes).
- **Equation numbers:** Best-effort extraction via right-margin geometry. Equation **bodies are not reconstructed** — PDF math rendering is lossy (bitmaps/glyphs, not LaTeX); source is unavailable post-compile. Noisy IDs remain possible on papers with complex multi-column layouts.
- **Sections:** Best-effort heading detection. Papers with non-standard heading styles (e.g., no caps/roman numerals in the text layer) may surface few or no sections.
- **Most reliable path:** Quote/page verification remains the robust anchor for review workflows.

## Test
    .venv/bin/pytest -v
