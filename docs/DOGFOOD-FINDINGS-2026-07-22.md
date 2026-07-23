# Dogfood findings — refereekit on arXiv:2106.00185 (2026-07-22)

First end-to-end run of the built tool (SP-A + SP-B) on a **real** paper (the
author's own public arXiv paper — zero confidentiality risk). Harness-side driving
+ in-session drafting (the pre-SP-D model). Goal: learn what real data breaks.

## What worked (validated on real content)
- **Ingest text:** all 9 pages extracted cleanly.
- **Quote/page verify (the common case):** correct — true quotes → PASS, false
  quotes → FAIL, claims locatable by page. This is the most-used verification kind
  in an actual review, and it holds.
- **Fact guarantee:** intact — nothing false passed; a fabricated "result" FAILed.
- **Draft flow:** produced a coherent report citing only verified anchors; the
  re-verify/flag step correctly left an unverbatim claim unanchored.

## What broke / is fixture-overfit (the payoff of dogfooding)
1. **Equation extraction is fixture-shaped.** `ingest.py`'s `\(\d{1,3}\)\s*$`
   regex found **0 equations** in a paper that has them: real PyMuPDF output puts
   the equation *number* off the line-end (separate span/line), so the line-anchored
   regex matches nothing. Needs block-geometry-based detection, not line-end regex.
2. **Figures never populated.** `figures` came back empty; the paper uses "FIG."
   (4×). This is the dead figure-caption loop flagged back in SP-A — confirmed inert
   on real data.
3. **Sections never populated.** Numbered headings don't surface as the word
   "Section"; no heading detection exists.
4. **Consequence for drafting:** because equation/figure anchors never enter the
   verified pool, any *real* equation/figure citation in a draft would be FLAGGED as
   "not in pool" — the guarantee stays sound but drafts would be **noisy** with false
   flags on a real paper. Quote/page citations are unaffected.
5. **Verbatim-match strictness:** `verify` requires exact substring match; referees
   paraphrase. Real usability nuance — consider fuzzy/normalized matching or
   surfacing "closest line" on FAIL.

## Recommended next cycle: ingest-hardening (small spec→plan→build)
- Equations: detect via text-block geometry / a broader pattern set; add a
  **real-paper fixture** (this paper) with known equation/figure/section ground
  truth so tests catch overfitting.
- Figures: populate from "FIG."/"Figure" caption lines (retire the dead loop).
- Sections: basic numbered/heading detection.
- Verify: consider normalized/fuzzy quote matching; on FAIL, report nearest line.
- This should land **before SP-C** — memory/drafting quality depends on a pool that
  actually contains the paper's equations and figures.

## Resolved by ingest-hardening (2026-07-22)

Branch `build/refereekit-ingest-hardening` addressed the extraction gaps:
- **Figures:** now reliable — detects exactly figures 1–4 on the real paper (handles both "FIG." and "Figure" prefixes); retired the dead caption loop.
- **Equation numbers:** best-effort via right-margin geometry — detects 21 equation numbers on the real paper (vs. 0 before). Note: **equation bodies not reconstructed** — PDF math rendering is lossy; LaTeX source is unavailable post-compile; noise IDs remain possible on papers with complex layouts.
- **Sections:** best-effort heading detection — this paper's headings don't surface as caps/roman in the PDF text layer, returning 0 sections by design (not a regression). Works on PDFs with recognizable heading structure.
- **Inline marker guard:** proven excludes text like "(1) first item" — the spec's fact-guarantee concern is resolved; equation detection uses right-margin bounding-box filtering.
- **Real-paper fixture:** `tests/fixtures/real_paper.pdf` committed as a regression guard with ground-truth assertions.

**Extraction limits** (see README): quote/page verification remains the most reliable path; figure detection is robust; equation and section extraction are best-effort due to PDF variability.

## Unchanged carry-overs
- SP-C: cross-paper memory write/recall (+ guard-threshold hardening before `store`
  accepts free text).
- SP-D: embedded agent loop (so the tool drives its own Q&A, not the harness).
- Deferred Minor: `report`/`editor_letter` shared verify helper (DRY).
- Diagrams: mark llm/memory/drafts as built (no longer "deferred").
