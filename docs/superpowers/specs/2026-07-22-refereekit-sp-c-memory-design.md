# refereekit SP-C (Phase 3) — Cross-Paper Memory Design Spec

**Date:** 2026-07-22
**Author:** Tzu-Chi Yen (with Claude Code)
**Status:** Approved design → ready for implementation planning
**Builds on:** SP-A + SP-B + ingest-hardening + verify-coherence (all merged to
`master`). Extends `refereekit/memory.py` and `refereekit/guard.py`.

---

## 1. Purpose

Give refereekit memory that persists across reviews: after a review, store the
referee's style/verdict patterns; recall them into future draft prompts (SP-B
already reads memory). SP-C is the phase that makes the memory **write** path
exist and makes it **safe** — memory-write is the first free-text egress path, so
the manuscript-leak guard becomes load-bearing here and is hardened accordingly.

Recall, the `Note` type, and the `MemoryStore` port already exist from SP-B; SP-C
adds the guarded write path, guard hardening, recall accumulation semantics, and
workflow wiring.

## 2. Prerequisites

None beyond the merged codebase. No LLM is used in SP-C (notes are
referee-authored, not distilled). No network.

## 3. Core decisions (locked)

| Area | Decision |
|---|---|
| What is stored | **Referee-authored structured notes only** (`Note(text, venue, kind)`), written/approved by the referee — never auto-extracted from the manuscript. Lowest leak risk by construction. |
| Store safety | `store(note, doc)` **requires** the current session `Document`; runs `guard.assert_no_manuscript(note.text, doc)` on every write, PLUS a short-text verbatim check (below). **Fails closed** (raises) if no doc is provided — there is no unguarded write path. |
| Guard hardening | Add a short-text verbatim-substring check to `guard`: text shorter than `n` words is rejected if it appears verbatim (normalized) in any page. Closes the known gap where `<n`-word notes produce no n-grams and slip through. |
| Recall semantics | `recall(venue, limit=20)` returns **distinct** note texts, **newest-first**, capped at `limit`. Requires a `created_at` column for ordering. Keeps draft prompts bounded and focused on recent patterns. |
| Schema migration | Adding `created_at` changes the SQLite schema. `SQLiteMemoryStore.__init__` migrates an existing SP-B `notes` table (no `created_at`) via `ALTER TABLE ADD COLUMN`, so old DBs upgrade cleanly instead of crashing. |
| Auto-distillation | **Deferred** to a later sub-cycle. Not in SP-C. |

## 4. Interfaces

- **guard** — add `is_verbatim_fragment(text, doc, *, n=8) -> bool`: True if `text`
  has fewer than `n` words AND its normalized form is a substring of any page's
  normalized text. `assert_no_manuscript(text, doc, *, n=8, max_overlap=1)` is
  extended to also raise `ManuscriptLeakError` when `is_verbatim_fragment` is True.
  (Long text keeps the existing n-gram-overlap check; short text gets the new one.)

- **memory** —
  - `Note(text, venue, kind="style", created_at=None)` — add optional `created_at`
    (ISO string; set at store time if absent).
  - `SQLiteMemoryStore.__init__(path)` — create table with columns
    `(text, venue, kind, created_at)`; if an existing table lacks `created_at`,
    `ALTER TABLE notes ADD COLUMN created_at TEXT`.
  - `SQLiteMemoryStore.store(note, doc)` — **doc is required** (a `Document`). Runs
    the guard on `note.text`; on pass, inserts with `created_at` = now (caller may
    pass a timestamp for determinism in tests). Raises if `doc is None`.
  - `SQLiteMemoryStore.recall(venue, limit=20)` — distinct `note.text` for the
    venue, ordered by `created_at` descending, at most `limit` rows.
  - The `MemoryStore` Protocol is updated to the new `store`/`recall` signatures.
    (SP-B's `recall(venue)` callers keep working via the default `limit`.)

  **Caller impact (verified):** no production code calls `memory.store` — SP-B was
  read-only by design. Only `tests/test_memory.py` calls the old `store(Note(...))`
  without a doc; that test is legitimately updated to the guarded `store(note, doc)`
  signature (it was asserting the now-replaced unguarded behavior). `recall` callers
  pass `venue` positionally, so the new `limit=20` default is backward-compatible.

- **cli** — `refereekit mem store --session S --venue V --kind K --text "..."`:
  loads the session's doc, constructs the `Note`, calls `store(note, doc)`; prints
  a confirmation, or a clean error + exit 2 if the guard rejects or no doc exists.
  Existing `mem recall --venue V` unchanged (uses the new default limit).

- **Determinism note:** because `store` stamps `created_at`, tests pass an explicit
  timestamp (the API accepts an optional `created_at`) rather than wall-clock, so
  recency ordering is deterministic and offline.

## 5. Data flow (memory write, at review wrap-up)

```
(end of a review; session has the Document + your verdict)
 → referee authors a style/verdict note (or approves a suggested one)
 → cli: mem store --session S --venue PRX --kind verdict --text "<your note>"
      doc = session.load_doc()
      store(Note(text, venue, kind), doc):
         guard.assert_no_manuscript(text, doc)      # raises on manuscript overlap
                                                    # (n-gram OR short verbatim)
         insert (text, venue, kind, created_at=now)
 → later review, drafting: recall(venue) feeds distinct recent notes into the
   SP-B draft prompt (already wired)
```

Manuscript text can never enter the store: the guard runs on every write and fails
closed without a doc. Notes are the referee's own patterns.

## 6. Confidentiality & error handling

- **Guarded write, fail-closed:** no doc → `store` raises; manuscript-overlapping
  text (n-gram or short verbatim) → `ManuscriptLeakError`. No unguarded path exists.
- **Local only:** SQLite on disk; no network, no LLM in SP-C.
- **Migration safety:** opening an old SP-B DB adds the column without data loss;
  opening a fresh DB creates the full schema.
- **CLI errors:** guard rejection or missing doc → clean stderr message + exit 2
  (matching ingest/verify), never a traceback.
- **Empty recall:** unknown venue → `[]` (unchanged).

## 7. Testing (all offline, deterministic)

- **guard short-text check:** a <n-word note that is a verbatim manuscript
  substring is rejected; a <n-word referee-authored note that is NOT in the
  manuscript passes; long-text n-gram behavior unchanged (regression).
- **store requires doc:** `store(note, None)` raises; `store(note, doc)` with a
  clean note inserts.
- **store rejects manuscript text:** a note overlapping the fixture is rejected.
- **recall dedup/recency/cap:** insert duplicates + >limit notes with controlled
  `created_at`; assert distinct, newest-first, ≤ limit.
- **schema migration:** create a DB with the old SP-B schema (no `created_at`),
  open it with the new store, confirm it migrates and store/recall work.
- **cli mem store:** guarded happy path writes; guard rejection → exit 2.
- Fixtures: the committed `sample_paper.pdf` / `real_paper.pdf`; no manuscript
  under review.

## 8. Build order (tasks land in the plan)

1. Guard: `is_verbatim_fragment` + extend `assert_no_manuscript`; tests.
2. Memory schema: `created_at` column + migration in `__init__`; tests.
3. `store(note, doc)` guarded + fail-closed; tests.
4. `recall(venue, limit)` dedup/recency/cap; tests (keep SP-B recall callers green).
5. CLI `mem store` (guarded, exit-2 on rejection); tests.
6. Full suite + README (memory write/recall + confidentiality note) + docs.

## 9. Out of scope / deferred

- LLM auto-distillation of notes from a review (later sub-cycle).
- Quote-match normalization (verbatim → fuzzy) — separate item.
- SP-D embedded agent loop.
- Non-SQLite `MemoryStore` adapters (mem0) — the port already allows it later.
