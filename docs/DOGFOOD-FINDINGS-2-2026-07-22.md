# Second dogfood pass — refereekit downstream flow on a real paper (2026-07-22)

Ran the flow AFTER ingest-hardening, targeting the downstream half (verify →
pool → draft) that had never run on a real, populated pool. Real paper:
arXiv:2106.00185 (author's own public paper).

## Setup confirmed
Hardened ingest now populates the pool on the real paper: figures 1–4, 21
equation numbers (real labels 1–7 + noise ids), 0 sections (by design). So
figure/equation verification could be exercised for the first time on real data.

## Findings

### Finding 1 (Important) — `verify --kind figure` ignores the now-populated figures
`ingest` extracts figures reliably (1–4), but `verify.py` still returns **FLAG for
every figure claim** regardless of existence:
- `verify figure 1` (exists) → FLAG
- `verify figure 9` (absent) → FLAG   ← identical response
The equation kind was wired to check existence against `doc.equations`
(verify.py:20-23), but the figure kind falls through to the catch-all
`FLAG` (verify.py:25). That catch-all predates having figure data (SP-A, when
`doc.figures` was always empty). Net: the figure-extraction capability we just
built is **dead at the verify layer** — inconsistent with equations.
Design question: should figure verify check *existence* (PASS/FAIL, like
equations) — a figure NUMBER either exists or not — while figure *content* claims
(“Fig. 3 shows X”) remain semantic/FLAG? Likely yes: mirror equations for
existence; keep content semantic.

### Finding 2 (Known limitation, now concretely demonstrated) — noise equation id passes
`verify equation 0` → **PASS**, because right-margin geometry extracted a junk
"0". Predicted by the ingest-hardening final review as the best-effort residual;
the dogfood makes it real. A referee citing "Eq. (0)" (or another noise id like
22/30) would get a false PASS. Bounded: requires a human to cite that exact junk
number, and the fact-guarantee never auto-certifies. But it means equation verify
can PASS on a non-label. Mitigation options: (a) filter obvious non-labels at
ingest (drop 0, and ids far outside a contiguous low sequence); (b) at verify,
only PASS equation ids within the detected contiguous run (e.g. 1..max-contiguous);
(c) accept + document (current stance).

### Unchanged / reconfirmed
- Quote/page verify: still solid (the reliable path).
- verify still requires verbatim substrings (referees paraphrase) — the
  quote-match normalization follow-up from dogfood #1 remains open.

## Suggested next actions (small, before SP-C)
1. Fix Finding 1: wire figure verify to existence (PASS/FAIL on figure number),
   keep content-claims semantic. Mirror the equation branch. + tests.
2. Address Finding 2: at minimum filter id "0"; consider contiguous-run filtering
   for equation labels; keep the documented best-effort caveat.
3. (Still open) quote-match normalization; report/editor DRY helper; diagram
   refresh. Then SP-C (memory) on a solid, coherent verify layer.

## Resolved by verify-coherence cycle (2026-07-22)

- **Finding 1 (figure verify):** RESOLVED. `verify --kind figure` now checks
  existence against `doc.figures` — PASS if the figure number exists, FAIL if not
  (mirrors the equation branch). Verified on the real paper: fig 1 -> PASS, fig 9 ->
  FAIL. Unknown kinds (e.g. "table") still FLAG. Figure *content* claims remain the
  referee's judgment.
- **Finding 2 (noise id "0"):** RESOLVED for the demonstrated case. Ingest now drops
  equation id "0" (never a real label); `verify equation 0` -> FAIL (was PASS).
  Conservative filter — higher noise ids (e.g. 22, 30) still possible and remain
  documented best-effort; real labels 1..7 unaffected.
- **Still open (deferred):** verbatim quote matching (paraphrase/nearest-line);
  contiguous-run equation filtering (chose the conservative drop-"0" only);
  report/editor DRY helper; diagram refresh.

## Resolved by typography folding (2026-08-15)

- **Verbatim quote matching:** RESOLVED, and it was a correctness bug rather
  than the usability nuance both dogfood passes recorded. `verify` compared raw
  codepoints, so a *correctly copied* quotation failed whenever extraction had
  handed back a ligature, a wide dash, a Unicode minus, a curly quote, a soft
  hyphen, or a word broken across a line. On the real fixture — 51 ligatures, 50
  dashes, 128 line-break hyphenations — `"a finite set of nodes"` returned FAIL.
  Comparison now folds typography on both sides via `refereekit/textnorm.py`.
  Folding only: every rule maps two spellings of the same characters onto one,
  so a genuine misquotation still FAILs, and a hyphen inside a line stays
  content (`58%` does not match `5-8%`).
- **Nearest line on FAIL:** RESOLVED. A failed quotation now reports the closest
  line on the page, so a slip in transcription is distinguishable from words
  that are absent. Diagnostic only; it never changes the verdict.
- **Leak guard had the mirror defect:** found while fixing the above. The same
  missing fold made `assert_no_manuscript` too *lax*: a short verbatim fragment
  retyped without the ligature was allowed into memory, defeating the
  fail-closed guarantee for exactly the text a referee is most likely to write.
  Now folds identically. The two are one bug with opposite signs, which is why
  the normalization is shared rather than duplicated.
- **Still open (deferred):** contiguous-run equation filtering (noise ids above
  the real range can still PASS); report/editor DRY helper; diagram refresh.
