# refereekit SP-B (Phase 2) — Drafting Design Spec

**Date:** 2026-07-22
**Author:** Tzu-Chi Yen (with Claude Code)
**Status:** Approved design → ready for implementation planning
**Builds on:** SP-A (Phase 1), merged to `master` — provides `types`, `ingest`,
`verify`, `guard`, `render`, `session`, `cli`.

---

## 1. Purpose

SP-B adds the drafting half of the workflow: turn a completed, fact-verified review
into a referee **report** and **editor-response letter** written in the referee's
own voice. It introduces the zero-retention LLM client that all prose generation
routes through, a read path to prior style/verdict memory, and a distilled style
guide. It preserves SP-A's core guarantee — **no factual claim reaches the output
unless it has been verified against the actual PDF.**

**In scope:** `llm` module (zero-retention, injectable backend); `drafts` module
(report + editor letter) with verified-pool + post-generation re-verification;
`memory` **read** path behind a `MemoryStore` port (SQLite adapter); a distilled
`style/STYLE.md`; CLI surface for drafting.

**Out of scope (later phases):** memory **write**/recall accumulation (SP-C);
`litsearch` (not required to draft); the embedded agent loop (SP-D). Per-section
length *choosing* stays in the harness driver (drafts exposes the parameters).

## 2. Prerequisites (verify outside the build)

1. **Anthropic zero-retention terms** confirmed for the account used (manuscript
   text is sent to the Claude API by `llm`).
2. **Journal referee AI-use policy** permits AI-assisted drafting under these terms.
   Both are the referee's responsibility; not enforced by code.

## 3. Core decisions (locked)

| Area | Decision |
|---|---|
| Draft engine | LLM-generated prose via the new `llm` module (not template-only). |
| Anchor integrity | **Verified-pool + post-generation re-verify.** Drafts assemble from an already-verified claim pool (PASS'd Q&A answers + verdict); the LLM is instructed to cite only from the pool; after generation, every anchor is re-extracted from the prose and re-verified against the PDF. Anything not in the pool, or that FAILs, is FLAGGED — never silently kept. |
| Style source | **Distilled `style/STYLE.md` only.** Raw past reports (confidential reviews of other manuscripts) are never sent to the LLM and never committed. STYLE.md is authored once in this cycle and holds voice rules + tiny anonymized snippets. |
| LLM backend | **Injectable.** `llm.complete(prompt, *, backend, manuscript_ok=False)`; real backend = zero-retention Anthropic client, test backend = deterministic fake. Fails **closed** if the endpoint is not marked zero-retention. |
| Testing | Offline via the fake backend (no keys, no network, no fixture text leaving). Real API = manual acceptance only. Fixture = the SP-A author-authored `sample_paper.pdf`. |
| Detail gate | Per-section length *choosing* stays in the harness driver; `drafts.report` accepts a `section_lengths` parameter. |

## 4. Module interfaces

- **llm** — `complete(prompt: str, *, backend: Complete, manuscript_ok: bool = False)
  -> str`.
  - `Complete` is a callable protocol: `(prompt: str) -> str`.
  - The real backend carries endpoint config; `complete` raises
    `RetentionError` (subclass of `RuntimeError`) unless the backend reports
    `zero_retention is True`. Fails closed: missing/false flag → raise, never send.
  - `manuscript_ok=False` is advisory metadata for callers/logging; the retention
    check is the hard gate.
  - `AnthropicBackend` (real) is thin and NOT unit-tested against the network;
    `FakeBackend(canned: str | Callable)` is used everywhere in tests.

- **memory** — `MemoryStore` (protocol) + `SQLiteMemoryStore(path)` adapter.
  - `recall(venue: str) -> list[Note]` where `Note = {text, venue, kind}`.
  - `store(...)` exists on the interface but SP-B only exercises `recall`
    (write path is SP-C). SP-B's `recall(venue)` takes only a short referee-authored
    venue string, so the guard is not the load-bearing risk here; the meaningful
    guarding of free-text notes belongs to `store` in SP-C. SP-B still routes any
    caller-supplied free text through `guard.assert_no_manuscript` for defense in
    depth, but does not manufacture manuscript-bearing paths that don't exist yet.
  - A `Mem0MemoryStore` can replace `SQLiteMemoryStore` later via one config point.

- **drafts** — consumes verified content + STYLE.md + memory, produces prose.
  - `build_pool(session) -> Pool` — gathers the verified claim pool: the PASS'd
    Q&A answers recorded in the session plus the verdict from `state.json`.
    `Pool = {claims: list[Claim], verdict: dict, qa: list[dict]}`.
  - `report(session, verdict, section_lengths: dict, *, backend, style_path) -> Draft`
  - `editor_letter(session, answers: dict, *, backend, style_path) -> Draft`
  - `Draft = {text: str, flags: list[Flag]}` where `Flag = {anchor, reason}` lists
    every anchor in the generated prose that was not in the pool or failed
    re-verification. A Draft with flags is still returned (so the referee sees it),
    but the flags are surfaced prominently.
  - Internal pipeline (both methods): assemble prompt (STYLE.md + pool +
    verdict/answers + section lengths) → `llm.complete(..., manuscript_ok=True)` →
    extract anchors from the returned prose → `verify` each against the session's
    Document → partition into kept / flagged.

- **style** — `load_style(path) -> str` (reads `style/STYLE.md`). No raw reports.

## 5. Data flow (drafting half, continues SP-A)

```
(after SP-A Q&A loop; session has verified answers + Document)
 → [3 VERDICT]  ◇HUMAN GATE◇ verdict recorded to state.json           (SP-A)
 → build_pool(session)                     verified claims + verdict
 → [4 DRAFT]    drafts.report(session, verdict, section_lengths,
                    backend, style_path)
                  prompt = STYLE.md + pool + verdict + lengths
                  → llm.complete(prompt, manuscript_ok=True)   MS→zero-retention API ✓
                  → extract anchors → verify() each vs Document
                       in-pool & PASS → keep · else → FLAG
                  → Draft{text, flags}
 → [5 DETAIL]   ◇HUMAN GATE◇ per-section lengths chosen in driver → re-draft
 → [6 EDITOR]   drafts.editor_letter(session, answers, backend, style_path)
                  (same pipeline; a/b/c/d structure)
 → outputs: report text + editor letter text + any flags for referee review
 memory.recall(venue) feeds voice/verdict context into the prompts (read only)
```

Manuscript text flows only into `llm` (zero-retention). `memory` and any
`litsearch` (absent here) receive no manuscript text — enforced by `guard`.

## 6. Confidentiality & error handling

- **llm fails closed:** no zero-retention flag → `RetentionError`, nothing sent.
  Asserted by an adversarial test.
- **Style corpus:** only `STYLE.md` (distilled, anonymized) is read into prompts or
  committed. Raw past reports are neither sent nor committed; `.gitignore` keeps any
  raw-report directory out of the repo.
- **Anchor integrity:** the pool+re-verify pipeline guarantees no unverified anchor
  lands silently; failures become visible `flags`.
- **memory** input guarded against manuscript text (same guard as SP-A).
- **LLM backend error / rate limit:** surfaces as an exception to the driver; the
  session state is untouched so drafting can be retried. No partial draft written
  as if complete.
- **Empty pool** (no verified claims yet): `report` returns a Draft whose text notes
  that no verified content is available and whose flags list is empty — never
  fabricates citations to fill space.

## 7. Testing

- **Fixture:** the SP-A `tests/fixtures/sample_paper.pdf` (author-authored). No
  confidential manuscript.
- **llm (offline):** `FakeBackend` returns canned prose. Assert: (a) `RetentionError`
  when backend is not zero-retention (fail-closed); (b) a zero-retention fake passes
  and returns its canned text; (c) `manuscript_ok` plumbing does not bypass the gate.
- **drafts (offline):** with a `FakeBackend` whose canned prose contains a mix of
  in-pool anchors, an out-of-pool anchor, and a wrong-page anchor, assert the Draft
  keeps the valid ones and FLAGS the invalid ones (this is the core guarantee test).
  Assert the assembled prompt contains STYLE.md content and the pool, and excludes
  raw-report text. Assert empty-pool behavior.
- **memory (offline):** `SQLiteMemoryStore.recall(venue)` returns seeded notes;
  guard rejects manuscript-overlapping input.
- **No live API in the suite.** Real-API generation is a manual acceptance step,
  run against the fixture only.
- **STYLE.md authoring** is a human-reviewed task, not an automated test.

## 8. Build order (tasks land in the plan)

1. `style/STYLE.md` authored from the 5 past reports (referee-reviewed) + a
   `load_style` loader. (Prerequisite for drafting; raw reports stay out of the repo.)
2. `llm` module: `Complete` protocol, `RetentionError`, `FakeBackend`, fail-closed
   `complete`; then a thin real `AnthropicBackend` (not unit-tested vs. network).
3. `memory` read path: `MemoryStore` protocol + `SQLiteMemoryStore.recall`, guarded.
4. `drafts.build_pool` (gather verified pool from session).
5. `drafts.report` (prompt assembly + generate + extract + re-verify → Draft/flags).
6. `drafts.editor_letter` (a/b/c/d structure, same pipeline).
7. CLI surface (`refereekit draft` / `refereekit editor`) + full-suite + README +
   manual real-API acceptance on the fixture.

## 9. Reused assets

- SP-A modules (`types`, `verify`, `session`, `ingest`, `render`) — consumed as-is.
- `/Users/tzuchi/Documents/Workspace/reviews/writing_examples/` (5 past reports) —
  the *source* for distilling `STYLE.md`, read once during authoring; **never sent
  to the LLM and never committed**.
- The session's `state.json` + recorded Q&A answers — the verified-claim pool.

## 10. Follow-through

- SP-C: memory **write**/recall accumulation across reviews.
- SP-D: embedded agent loop (drop the harness driver).
- Carried-over guardrail from SP-A: **tune the `guard` n-gram threshold and
  adversarially re-test before any new egress path is wired** — `memory.recall` here
  is read-only and receives only referee-authored venue strings, but revisit the
  threshold when `store` (SP-C) begins accepting free-text notes.
