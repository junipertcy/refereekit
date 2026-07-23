# refereekit SP-D (Phase 4) — Embedded Review Loop Design Spec

**Date:** 2026-07-22
**Author:** Tzu-Chi Yen (with Claude Code)
**Status:** Approved design → ready for implementation planning
**Builds on:** SP-A + SP-B + ingest-hardening + verify-coherence + SP-C (all merged
to `master`). Adds `refereekit/agent/`; adds a `review` CLI command. Reuses all
existing modules; no new domain logic.

---

## 1. Purpose

Make refereekit **self-driving**: `refereekit review <pdf>` runs a complete review
in one process — ingest, summarize, an interactive Q&A loop, the two human gates,
and draft/editor output — without any external harness (Claude Code) orchestrating
the conversation. This is the phase that makes the tool fully standalone (the
original architecture's endpoint).

It is a **scripted orchestrator**, not an autonomous agent: the review SEQUENCE is
hardcoded (deterministic control flow); the LLM only fills in prose within each
step. This preserves the deterministic-orchestration ethos and testability that
kept SP-A–C clean, and keeps the LLM away from deciding which tools run.

## 2. Prerequisites

- Anthropic zero-retention terms confirmed (manuscript text reaches the LLM), same
  as SP-B. For the real `review` run, an API key + `REFEREEKIT_ZERO_RETENTION=1`.
- Tests need neither (they use `FakeBackend` + scripted I/O).

## 3. Core decisions (locked)

| Area | Decision |
|---|---|
| Loop shape | **Scripted orchestrator**, fixed pipeline: ingest → summarize → Q&A REPL → verdict gate → draft → detail gate → editor. LLM fills prose within steps; the loop controls flow. NOT an autonomous/tool-calling agent (explicitly rejected). |
| I/O | **Injectable** `input_fn`/`output_fn` (default real `input`/`print`). Interactive use wires stdin/stdout; tests inject scripted inputs + capture outputs. The REPL and both gates are thus deterministically testable offline. |
| Multi-turn | The loop keeps a running **transcript** (prior Q&A + relevant doc slices) and rebuilds ONE prompt per question → `llm.complete(...)`. `llm` and its zero-retention guard are **unchanged** — a single audited egress path. Each answer's anchors are re-verified via `verify`. |
| Reuse | ingest, verify, render, drafts (report/editor, memory-aware from SP-C), session, guard, memory — the loop is orchestration only; no new domain logic. |
| Backend selection | Reuse SP-B's `_backend()` env-var pattern (`REFEREEKIT_FAKE` for tests; zero-retention Anthropic for real). |
| Transcript confidentiality | The transcript is manuscript-bearing → persisted ONLY in the session working dir (git-ignored), and sent only to `complete()`. Never to memory or Exa. No new egress path. |

## 4. Interfaces

New package `refereekit/agent/` (e.g. `refereekit/agent/__init__.py` +
`refereekit/agent/loop.py`):

- `run_review(pdf_path, *, backend, session_dir, input_fn=input, output_fn=print,
  style_path="style/STYLE.md", memory=None, venue=None) -> ReviewResult` — runs the
  full pipeline. Steps:
  0. `ingest(pdf_path)` → save to a `Session(session_dir)`.
  1. **Summarize:** `complete(summary_prompt + doc_context, backend, manuscript_ok=True)`;
     `output_fn` the summary. (Literature context via Exa is out of scope for SP-D —
     it is not yet built as a module; the loop does not call it.)
  1b. **Init HTML:** call `render.init_page(session, title)` once before the Q&A
     loop, so `append_qa` has a page to prepend into (mirrors how the harness drove
     render in SP-A/SP-B).
  2. **Q&A REPL:** repeat until the referee enters a sentinel (e.g. blank line or
     `/done`):
     - `q = input_fn(prompt)`; if sentinel → break.
     - build `prompt = doc_context + transcript + q`; `ans = complete(prompt, backend,
       manuscript_ok=True)`.
     - extract anchors from `ans`; `verify` each; annotate/flag failures
       (reuse the drafts/verify machinery — never show an unverified anchor as verified).
     - `render.append_qa(session, q, ans)`; `output_fn(ans)`; append `(q, ans)` to
       transcript.
  3. **Verdict gate (HUMAN):** prompt via `input_fn` for recommend/venue/major-minor;
     record to `session` state (as SP-A/SP-B expect for drafts).
  4. **Draft:** `drafts.report(session, verdict, section_lengths, backend=backend,
     style_path=style_path, memory=memory, venue=venue)`.
  5. **Detail gate (HUMAN):** prompt via `input_fn` for per-section lengths; re-draft
     if changed.
  6. **Editor:** `drafts.editor_letter(session, answers, backend=backend,
     style_path=style_path, memory=memory, venue=venue)` (answers gathered via
     `input_fn`).
  Writes `report.txt` / `editor.txt` into the session; returns a `ReviewResult`
  (paths + any flags + the verdict).

- `ReviewResult` dataclass: `report_path`, `editor_path`, `flags: list`, `verdict: dict`.

- `_doc_context(doc, transcript, question) -> str` — assembles the bounded prompt
  context (doc slices + transcript + question). Pure/testable.

- **cli** — `refereekit review <pdf> --session S [--venue V] [--db PATH]
  [--style PATH]`: selects `_backend()`, constructs an optional `SQLiteMemoryStore`
  (default `<session>/memory.db`) as `memory`, calls `run_review(...)` with real
  stdin/stdout; prints result summary. Guard/LLM/IO errors → clean stderr + exit 2.

- No change to `llm`, `guard`, `verify`, `ingest`, `session`, `memory`, `drafts`
  signatures — SP-D only orchestrates them.

## 5. Data flow

```
refereekit review paper.pdf --session S --venue PRX
 → run_review(pdf, backend=<real|fake>, session_dir=S, memory=<sqlite>, venue=PRX):
    ingest → session.save_doc
    summarize:  complete(prompt+doc, manuscript_ok=True)  MS→zero-retention LLM ✓
    Q&A REPL (until sentinel):
        q = input_fn()
        prompt = doc_context + transcript + q
        ans = complete(prompt, manuscript_ok=True)         MS→zero-retention LLM ✓
        verify(anchors) ; render.append_qa ; output_fn(ans); transcript += (q,ans)
    ◇verdict gate◇ input_fn → session state
    drafts.report(..., memory, venue)   ← recall(venue) feeds prior notes (SP-C)
    ◇detail gate◇ input_fn → section lengths
    drafts.editor_letter(...)
 → report.txt, editor.txt, live index.html in the session dir
```

Manuscript text reaches only `complete()` (zero-retention) and the local session
dir. Memory recall is read-only into the prompt; nothing manuscript-derived is
written to memory or Exa.

## 6. Confidentiality & error handling

- **Single egress path unchanged:** all manuscript text still flows through the one
  audited `llm.complete` (zero-retention, fail-closed). The transcript is held in
  memory during the run and any persistence is inside the git-ignored session dir.
- **Memory stays guarded:** the loop never writes manuscript text to memory; recall
  is read-only. (Storing notes remains the explicit guarded `mem-store` path.)
- **Anchor integrity in Q&A:** answers' anchors are re-verified against the doc;
  unverified anchors are flagged to the referee, never presented as confirmed.
- **Errors:** ingest failure / LLM error / bad input → clean message, and the loop
  saves session state so a run is resumable where practical; the CLI returns exit 2
  on setup errors (missing pdf/session), never a traceback.
- **Sentinel/empty Q&A:** entering the sentinel immediately (no questions) is valid —
  proceeds to the verdict gate; a review with zero verified claims drafts honestly
  (as SP-B already handles).

## 7. Testing (offline, deterministic)

- **Full-loop happy path:** `run_review(real_paper.pdf, backend=FakeBackend(canned),
  input_fn=iter(script), output_fn=capture, session_dir=tmp, memory=…, venue="PRX")`
  where `script` = [a question, the sentinel, verdict fields, section-length choices,
  editor answers]. Assert: summary emitted; Q&A answer emitted + appended to HTML;
  `report.txt` and `editor.txt` written; `ReviewResult` populated; recalled memory
  note present in the draft prompt (thread a capturing backend or assert on output).
- **Anchor flagging in Q&A:** a canned answer citing a bogus anchor is flagged, not
  shown as verified.
- **Gates honored:** scripted verdict + section-length inputs land in the outputs.
- **Sentinel-first:** immediate sentinel → no Q&A, proceeds to gates, still drafts.
- **No live API / no network** in the suite; `input_fn`/`output_fn` fully injected.
- **CLI `review`:** with `REFEREEKIT_FAKE=1` + scripted stdin (monkeypatched or via a
  small input list), the command runs end-to-end and writes outputs; setup error →
  exit 2.
- Fixtures: committed `real_paper.pdf`; no manuscript under review.

## 8. Build order (tasks land in the plan)

1. `_doc_context` + transcript prompt assembly (pure, tested first).
2. Q&A REPL step: injectable I/O loop, per-question complete → verify → render →
   transcript; sentinel handling; anchor flagging. Tested with FakeBackend + scripted
   input.
3. Verdict + detail gates via `input_fn`; wire into session state.
4. `run_review` end-to-end: ingest → summarize → Q&A → gates → drafts; `ReviewResult`.
5. CLI `review` command (backend/memory selection; exit-2 on setup error).
6. Full suite + README (`review` usage, standalone note) + manual real-API acceptance
   documented (fixture only).

## 9. Out of scope / deferred

- **Autonomous/tool-calling agent** — explicitly rejected (this is scripted).
- **Literature (Exa) in the loop** — `litsearch` is not a built module; SP-D does not
  add it. (Summarize uses the manuscript + LLM only.)
- **Quote-match normalization** — separate deferred item.
- **Multi-turn chat API in `llm`** — rejected; transcript-in-prompt instead.
- **Resumable mid-Q&A checkpointing** beyond what `session` state already provides.
