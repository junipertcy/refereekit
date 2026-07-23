# refereekit — Design Spec

**Date:** 2026-07-22
**Author:** Tzu-Chi Yen (with Claude Code)
**Status:** Approved design → ready for implementation planning

---

## 1. Purpose

`refereekit` is a standalone, harness-agnostic command-line tool that automates the
recurring academic paper-review workflow of a serial referee: ingest a submitted
PDF, summarize it with published-literature context, support an interactive Q&A
loop with fact-verified answers, help form a recommendation, and draft the referee
report and editor-response letter in the referee's own writing voice.

It is built **portable-core-first**: all value lives in a Python package with a plain
CLI, so it survives a change of agent harness (Claude Code today, pi.dev or a bare
CLI later). The harness is a thin, swappable driver.

**Non-goals (this system):** OCR of scanned PDFs; multi-referee collaboration;
submitting reviews to journal portals; training/fine-tuning any model.

## 2. Prerequisites (verify outside the build)

1. **Anthropic zero-retention terms** must be confirmed for the account used, since
   manuscript text is sent to the Claude API (see §5).
2. **Journal referee AI-use policy** must permit AI-assisted reviewing under these
   conditions. Both are the referee's responsibility, not enforced by code.

## 3. Core decisions (locked)

| Area | Decision |
|---|---|
| Scope | One spec for the whole system; phased build order SP-A→D. |
| Confidentiality | Manuscript text may travel **only** to a zero-retention Claude API; never to Exa or any persisted store. Guard fails **closed**. |
| LLM backend | A no-retention cloud API (Claude) is trusted for manuscript reasoning. Truly-local LLM is out of scope for now. |
| Interaction | Conversational with checkpoints. Two human gates: verdict, per-section detail. |
| Memory | Local SQLite behind a swappable `MemoryStore` interface (mem0 adapter droppable later via config). Stores style/verdict notes keyed by venue; **never** manuscript text. |
| Verification | Every factual anchor auto-verified against the extracted PDF. Mechanical anchors → PASS/FAIL (auto-fix + recheck on FAIL). Semantic claims → FLAG for human confirmation. |
| Architecture | Standalone CLI (chosen over harness-embedded). Reached in phases: Phase 1 = deterministic tool-CLI + Claude Code driving the dialogue; later phase embeds the LLM loop for full independence. |
| Testing | Fixture = a short, author-authorized sample paper derived from arXiv:2106.00185. **No confidential manuscript under review is ever committed or used as a fixture.** |

## 4. Architecture & module boundaries

```
refereekit/                        portable core — all value lives here
  ingest/     PDF → text, figures, equations, page-map        [deterministic]
  verify/     claim → PASS | FAIL | FLAG against Document       [deterministic]
  litsearch/  Exa queries — PUBLISHED lit only, guarded         [network, safe]
  render/     live-reload HTML + MathJax Q&A page               [deterministic]
  memory/     MemoryStore port; SQLiteMemoryStore adapter now   [local only]
  drafts/     report + editor-letter templates (referee voice)  [deterministic]
  llm/        thin Claude-API client, zero-retention guard      [network, MS-ok]
  guard/      assert_no_manuscript() — used by litsearch+memory  [safety]
  session/    per-paper working dir (doc.json, index.html, drafts, state.json)
  cli.py      `refereekit <command>` — thin wrapper over the module APIs

drivers (thin, swappable — NOT where value lives):
  Phase 1: Claude Code drives conversation, calls refereekit commands
  Phase 4: refereekit/agent/ — embedded LLM loop → fully standalone
```

Each module is a plain Python API *and* a CLI subcommand; the CLI wraps the API so
the harness and the future embedded loop call the same functions. Each unit is
independently testable and has one clear purpose.

## 5. Module interfaces

- **ingest** — `ingest(pdf_path) → Document`.
  `Document = {pages:[{n,text,blocks}], figures:[{id,page,caption}],
  equations:[{id,page,latex_or_text}], sections:[{title,page}]}`.
  Built from the existing PyMuPDF scripts. Cached to `session/doc.json`.
  CLI: `refereekit ingest paper.pdf`

- **verify** — `verify(claim, Document) → Verdict`.
  `claim = {text, kind: page|equation|figure|quote, anchor}`;
  `Verdict = {status: PASS|FAIL|FLAG, evidence}`. Mechanical kinds judged
  deterministically; semantic kinds always FLAG.
  CLI: `refereekit verify --session S`

- **litsearch** — `search(query) → [result]`. Wraps Exa. Input passed through
  `guard.assert_no_manuscript` first.
  CLI: `refereekit lit "topic query"`

- **render** — `append_qa(session, question, answer_html)` + `serve(session, port)`.
  MathJax auto-reload page (from this session's `index.html`). Port auto-increments
  if busy.
  CLI: `refereekit serve --session S --port 8888`

- **memory** — `recall(venue) → notes` / `store(note, venue)`.
  `MemoryStore` interface with `SQLiteMemoryStore` adapter. Style/verdict notes only,
  keyed by venue. Input guarded against manuscript text.
  CLI: `refereekit mem recall --venue PRX`

- **drafts** — `report(session, verdict, section_lengths) → text` /
  `editor_letter(session, answers) → text`. Fills referee-voice templates (from
  `style/` corpus + memory) with verified content. Every embedded anchor re-run
  through `verify` before it lands.

- **llm** — `complete(prompt, *, manuscript_ok=False) → text`. The sole
  manuscript-bearing network path. Refuses to run unless endpoint config carries
  `zero_retention: true`.

- **guard** — `assert_no_manuscript(text, Document) → None | raises`. Rejects any
  string overlapping the ingested Document beyond an n-gram threshold (threshold set
  at plan time). Called inside `litsearch` and `memory` so it cannot be bypassed.
  Pure function, no I/O; heavily unit-tested (§8).

- **session** — per-paper working dir: `doc.json`, `index.html`, `answers/`,
  `drafts/`, `state.json` (verdict, choices, progress). Runs are resumable.

## 6. Data flow (one review)

```
"review paper.pdf"
 → [0 INGEST]   ingest → session/doc.json                         (local)
 → [1 SUMMARY]  llm.complete(summary+doc, manuscript_ok=True)      MS→Claude API ✓
                litsearch.search(derived topics)                  topics→Exa ✓ (no MS)
                memory.recall(venue)                              prior style/verdict
 → [2 Q&A LOOP] (repeat until satisfied)
                llm.complete(q+doc slices, manuscript_ok=True) → answer w/ anchors
                verify(each anchor): PASS keep · FAIL auto-fix+recheck · FLAG→user
                render.append_qa → live HTML reloads
 → [3 VERDICT]  ◇HUMAN GATE◇ agent proposes {recommend,venue,major/minor}; you decide
 → [4 DRAFT]    drafts.report(...) — every claim re-verified before landing
 → [5 DETAIL]   ◇HUMAN GATE◇ per-section length menu → re-render
 → [6 EDITOR]   drafts.editor_letter(a/b/c/d answers)
 → [WRAP]       memory.store(style corrections + verdict, venue)  your notes only ✓
                outputs: review_draft.txt, editor_response.txt, session/ archive
```

Manuscript text flows only rightward into `llm`. Verification is inline (at
production time), not a final pass. Both human gates persist to `state.json`.

## 7. Confidentiality & error handling

**Guard (must not fail):**
- `guard.assert_no_manuscript(text)` sits inside `litsearch` and `memory`; rejects
  any string overlapping `doc.json` beyond an n-gram threshold. No caller can bypass.
- `llm.complete(manuscript_ok=True)` is the only manuscript-accepting function and
  refuses non-zero-retention endpoints. **Fails closed** on misconfiguration.
- Both rules are asserted by adversarial tests (§8).

**Error modes:**
- Ingest fails / no text layer → hard stop ("no extractable text; OCR out of scope").
  Never proceed on empty extraction.
- verify FAIL → auto-correct + recheck once; if unresolved, drop + log, never show.
- verify FLAG → surfaced inline; never silently accepted.
- Exa/network down → literature step degrades gracefully; never blocks the review.
- LLM API error → retry w/ backoff; on persistent failure, save state + exit resumably.
- Server port busy → auto-increment, report chosen port.

## 8. Testing

- **Fixture:** `tests/fixtures/sample_paper.tex` → compiled `.pdf`, a short
  (~1–2 page) paper derived from arXiv:2106.00185 (author-authorized), with planted
  ground truth: a known quote on a known page, an existing Eq. (3) and a
  non-existent Eq. (9), a figure caption, a deliberate `the the` typo, a
  reserved-word edge case. Ground truth is exact because we author it.
- **Unit (deterministic core):** ingest, verify, guard, memory, render tested against
  the fixture as regression assertions.
- **Guard tests (mandatory, adversarial):** manuscript text is rejected by
  litsearch/memory; llm refuses a non-zero-retention endpoint. Fail the build if
  confidentiality regresses.
- **verify golden set:** a table of (claim → PASS/FAIL/FLAG) built entirely from the
  fixture's planted ground truth (a quote on the wrong page; a nonexistent equation;
  a semantic claim that must FLAG). No real manuscript is cited.
- **LLM-dependent stages:** smoke-tested only (runs, non-empty, all output anchors
  pass verify). No exact-prose assertions.
- **Acceptance:** run Phase 1 end-to-end on a real paper.

## 9. Build phases

- **SP-A (Phase 1):** ingest + verify + render + guard + session + cli. Claude Code
  drives dialogue. Delivers a runnable review pipeline. **This is the first milestone.**
- **SP-B (Phase 2):** drafts (report + editor letter) + memory *read* + style corpus.
- **SP-C (Phase 3):** memory *write*/recall across reviews (SQLite adapter).
- **SP-D (Phase 4):** embedded agent loop (`refereekit/agent/`) → drop the harness
  driver; fully standalone. Highest-effort, deferred last.

## 10. Final step

Update `diagrams/index.html` (the five views) to reflect this design, and add a
dedicated **"why it's built this way"** panel documenting the intentional
engineering decisions: (1) standalone portable core + thin swappable glue;
(2) confidentiality enforced architecturally (MS text only to zero-retention API,
guarded away from Exa/memory); (3) inline PASS/FAIL/FLAG verification at production
time; (4) two human gates, resumable via state.json; (5) MemoryStore port + adapter
(SQLite now, mem0 later); (6) phased build, embedded loop last.

## 11. Reused assets (already in the working dir)

- `analyze.py`, `count_para*.py`, `locate*.py`, `para_full.py` → seed `ingest`.
- `verify_all.py`, `verify2.py`, `verify3.py` → seed `verify`.
- The session's MathJax auto-reload Q&A page → seed `render`.
- A local corpus of the referee's past reviews (`~/reviews/writing_examples/`, 5 past
  reviews) → the `style/` corpus and the `drafts` voice templates. (Per-review outputs
  are never committed and are not reused as assets.)

Note: the helper scripts above are one-off exploration tooling; they are git-ignored
and are re-implemented cleanly inside the package rather than committed as-is.
- `diagrams/` → updated in the final step.
