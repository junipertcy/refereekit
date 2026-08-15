# Harden the verification guarantees

## Why

refereekit's value is a guarantee, not a feature: an anchor that reads PASS is
in the paper, manuscript text does not leave the machine except where the
referee has said it may, and a citation the tool blesses can be trusted in a
report that goes to an editor under the referee's name.

Over one working session, seven separate controls turned out to look enforced
while not being enforced:

| Control | How it failed |
|---|---|
| Quotation verification | A correctly copied quote returned FAIL (PDF ligatures, dashes, line-break hyphens) |
| Manuscript leak guard | The same fragment retyped plainly was *allowed* into memory |
| Venue policy on `or-draft` | Never checked the venue `or-fetch` had already recorded |
| Venue policy on `or-responses` | Left ungated; consumed 18 real NeurIPS notes |
| Repository hygiene | Manuscript patterns anchored to the root; `docs/paper.pdf` was committable |
| Transport selection | An unknown `REFEREEKIT_BACKEND` silently became the default |
| Deployment defaults | A fabricated Vertex model id shipped in the package |

Five are fixed. Two remain, and — more importantly — nothing in the suite pins
the *class*, so the next one arrives the same way.

## What changes

**1. An equation anchor outside the extracted contiguous run stops passing.**
Equation ids come from right-margin geometry, which is best-effort. On the real
fixture it yields 20 numeric ids of which only `1..7` are labels; the other 13
are noise (`18, 19, 20, 22, 30, 39, 44, 50, 55, 82, 311, 490, 500`). Today
`verify --kind equation --anchor 500` returns **PASS**. This is the dangerous
direction: a false FAIL annoys the referee, a false PASS puts a citation to a
nonexistent equation into a report with the tool's blessing.

**2. No deployment ships a model id that has not been run.** The `vertex` entry
carries `claude-opus-4-8@20260115`, which was invented. A plausible-looking
fabricated default fails confusingly instead of obviously.

**3. The venue gate becomes a property of the command surface, not a list.**
Five of eleven commands can reach a model with manuscript text. All five are
gated today, by hand, one call site at a time — which is exactly how
`or-responses` shipped ungated. A sixth command must inherit the refusal rather
than opt into it.

## Non-goals

- **The retention attestation.** `REFEREEKIT_ZERO_RETENTION=1` is a claim the
  referee makes that no code can check, and it is a two-state flag over a
  three-tier world (ZDR / commercial / consumer). Real, but a separate change.
- **Extraction accuracy.** This change narrows what verification will *assert*;
  it does not improve what ingest finds. Equation bodies stay unreconstructed.
- **`report`/`editor_letter` deduplication.** Measured at 11 and 9 lines, 0.56
  similarity. Extracting a shared helper from that is churn; closing as won't-do.
- **Docs and process** — diagram refresh, branch merge, converting
  `work/run_review_bedrock.py`. No behaviour to state, so no requirement.

## Impact

- `refereekit/verify.py`, `refereekit/llm.py`, `refereekit/cli.py`
- New: a suite-level test that discovers manuscript-sending commands rather than
  listing them
- One behaviour change a referee will notice: equation anchors above the
  contiguous run now FAIL. On the real fixture no genuine label is affected.
