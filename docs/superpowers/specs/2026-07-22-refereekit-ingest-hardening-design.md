# refereekit — Ingest Hardening Design Spec

**Date:** 2026-07-22
**Author:** Tzu-Chi Yen (with Claude Code)
**Status:** Approved design → ready for implementation planning
**Builds on:** SP-A + SP-B (merged to `master`). Modifies `refereekit/ingest.py`.
**Motivated by:** `docs/DOGFOOD-FINDINGS-2026-07-22.md` — first real-paper run found
ingest extracted 0 equations / 0 figures / 0 sections.

---

## 1. Purpose

Make `ingest` work on real papers, not just the synthetic fixture. Dogfooding on a
real arXiv PDF showed the extractors were fixture-overfit: they found nothing of the
paper's equations, figures, or sections. This cycle hardens extraction so that
`verify`'s equation/figure anchors resolve against real content, and adds a
committed real-paper fixture so tests catch overfitting in future.

Quote/page verification already works on real papers and is unchanged.

## 2. Investigation findings (evidence that shaped scope)

On `arXiv:2106.00185` (9 pp., text layer intact — NOT a scanned PDF):
- **Equation numbers are not `(N)` text tokens.** Zero standalone `(N)` spans. The
  only `(1)`/`(2)` in the text are inline list markers ("if (1) … and (2) …") —
  extracting those as equations would be a FALSE POSITIVE. Real labels appear as
  **bare right-margin numeric spans** (LaTeX `\begin{equation}` typesetting).
- **Right-margin geometry is NOISY.** 40 right-margin bare-number spans exist, but
  they include line numbers / reference marks (e.g. 18, 22, 30, 39) and duplicates —
  not a clean equation-label signal.
- **Equation bodies are lossy** (fragments across lines; pages 3–4 have 1000+ vector
  drawings — much math is rendered as paths, not text). But `verify` never uses the
  body — only the number — so lossy bodies do not block the capability.
- **Figures are clean:** lines match `FIG. N.` exactly for N = 1..4.
- **Conclusion:** OCR / vision is NOT needed (it would only help reconstruct bodies,
  which we don't verify). Geometry recovers numbers locally and deterministically.

## 3. Core decisions (locked)

| Area | Decision |
|---|---|
| Figures | **Reliable feature.** Extract from `FIG. N.` caption lines. Retire the dead `pass` loop. Fixture asserts figures exactly (1..4). |
| Sections | **Basic heading detection.** Emit `Section` entries from heading-like lines. Sanity-bounded in tests. |
| Equations | **Best-effort, documented approximate.** Right-margin bare-number span geometry, filtered to exclude inline list markers and obvious non-labels. Fixture *sanity-bounds* (finds ≥1 plausible label; invents no figures), NOT exact count — geometry is noisy. |
| Equation bodies | Not reconstructed (lossy in PDF). `verify --kind equation` checks existence of the number only, as today. |
| OCR / vision / LLM in ingest | **Excluded.** ingest stays pure, local, offline, deterministic. |
| Real-paper fixture | Commit `tests/fixtures/real_paper.pdf` = arXiv:2106.00185 (author's own public paper). Golden test guards against overfitting. |
| Quote/page verify | Unchanged (works). Quote-match normalization is a DEFERRED follow-up, not this cycle. |
| Fact guarantee | Preserved: filtering prevents false-positive equations; nothing false is certified. |

## 4. Interfaces

`ingest(pdf_path) -> Document` — signature unchanged; internals hardened.

New private helpers in `refereekit/ingest.py`:
- `_extract_figures(page_text: str, page_no: int) -> list[Figure]` — regex
  `^\s*FIG\.\s*(\d+)\.\s*(.*)` per line → `Figure(id=N, page=page_no, caption=...)`.
- `_extract_sections(page_text: str, page_no: int) -> list[Section]` — detect
  heading lines (e.g. all-caps short lines, or `N. Title` / roman-numeral headings)
  → `Section(title, page)`. Conservative: prefer missing a heading over emitting
  body text as a section.
- `_extract_equation_numbers(page: fitz.Page) -> list[Equation]` — use
  `page.get_text("dict")` span geometry: a span whose text is a bare integer, whose
  x0 is in the right margin (> ~0.85 × page width), and which is NOT part of an
  inline `(N)` token. `Equation(id=N, page, body="")`. Documented best-effort.
- Existing `to_json`/`from_json` unchanged (Document shape is stable).

The `Document`/`Figure`/`Equation`/`Section` dataclasses are unchanged.

## 5. Confidentiality & scope guards

- The committed fixture is the author's own **public** paper — no manuscript under
  review. The dogfood working copy (`work/`) stays git-ignored.
- `ingest` remains offline/deterministic: no network, no LLM, stdlib + PyMuPDF only.
- No manuscript identifier in any committed file, test, or message.

## 6. Testing

- **Real-paper fixture** `tests/fixtures/real_paper.pdf` (arXiv:2106.00185).
  - `figures`: assert exactly ids {1,2,3,4} extracted (clean signal).
  - `equations`: assert best-effort bound — at least 1 plausible label extracted AND
    no inline-list-marker false positive (e.g. not fooled into calling the "(1)…(2)"
    list sentence equations); do NOT assert an exact count.
  - `sections`: assert at least the top-level sections detected; sanity-bounded.
  - Regression intent: this test FAILS if extraction silently returns empty again.
- **Synthetic fixture** (existing `sample_paper.tex`) unit tests stay green; extend
  only if needed to cover the figure/section helpers deterministically.
- **False-positive guard (equations):** a unit test feeds text containing an inline
  "(1) … (2)" list and asserts those do not become equations.
- All tests offline; no OCR/network.

## 7. Build order (tasks land in the plan)

1. Commit the real-paper fixture PDF + a `real_doc` pytest fixture (ingest it once).
2. `_extract_figures` + wire into `ingest`; assert FIG 1..4 on the real fixture;
   retire the dead loop.
3. `_extract_sections` + wire in; sanity-bound on the real fixture.
4. `_extract_equation_numbers` (geometry, filtered) + wire in; best-effort bound on
   the real fixture + the inline-marker false-positive unit test.
5. Full suite + update `docs/DOGFOOD-FINDINGS` status + README note on extraction
   limits (figures reliable; equations best-effort; bodies not reconstructed).

## 8. Out of scope / deferred

- Quote-match normalization (fuzzy/nearest-line on FAIL) — real dogfood nuance,
  next cycle.
- Equation body reconstruction, OCR, vision-LLM ingest.
- SP-C (memory write) and SP-D (embedded loop) — unchanged roadmap; this cycle lands
  before SP-C so the verified pool actually contains figures/equations.
