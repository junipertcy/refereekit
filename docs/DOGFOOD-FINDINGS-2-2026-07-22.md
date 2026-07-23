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
