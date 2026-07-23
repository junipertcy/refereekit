# refereekit SP-C (Phase 3) — Cross-Paper Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Persist referee-authored style/verdict notes across reviews and recall them into drafts — with a guarded, fail-closed write path so manuscript text can never be stored.

**Architecture:** Extend `refereekit/guard.py` (short-text verbatim check), `refereekit/memory.py` (created_at + migration, guarded `store(note, doc)`, dedup/recency `recall`), and `refereekit/cli.py` (add a `mem` subcommand group with `store` and `recall`). No LLM, no network; SQLite on disk. Notes are referee-authored only.

**Tech Stack:** Python 3.14, stdlib (`sqlite3`, `re`, `datetime`), PyMuPDF (already used), pytest.

## Global Constraints

- **Confidentiality:** No manuscript-under-review text/identifier committed. Memory-write is a guarded egress path: `store` requires the session `Document`, runs the guard on every note, and **fails closed** (raises) with no doc. No unguarded write path may exist.
- **No auto-extraction:** notes are referee-authored; SP-C does not distill notes from the manuscript, and uses no LLM.
- **Dependency-light:** stdlib + PyMuPDF only.
- **Backward compatibility:** opening an existing SP-B `notes` DB (no `created_at`) must migrate, not crash. `recall` callers passing only `venue` must keep working.
- **Determinism:** tests pass explicit `created_at` timestamps (never wall-clock) so recency ordering is deterministic and offline.
- **Python:** target 3.14; run tools as `.venv/bin/python`, `.venv/bin/pytest`.
- **TDD:** failing test first; commit per task.

## Ground truth / caller impact (verified)

- No production code calls `memory.store` (SP-B was read-only). Only `tests/test_memory.py` calls the old `store(Note(...))`; that test is legitimately updated to the guarded signature.
- `recall` callers pass `venue` positionally → new `limit=20` default is backward-compatible.
- **There is NO existing `mem` CLI subcommand** (SP-B surfaced only `draft`/`editor`; memory-read was internal to drafts). Task 5 adds both `mem store` and `mem recall`.
- guard fixture facts: `real_paper.pdf` page 1 contains "prescribed degree-size sequences" (a >n-word verbatim phrase) and shorter verbatim fragments; a note like "PRX: lean accept-after-major" is NOT in the manuscript.

---

### Task 1: Guard — short-text verbatim check

**Files:**
- Modify: `refereekit/guard.py`
- Test: `tests/test_guard_shorttext.py`

**Interfaces:**
- Consumes: `Document` (pages with `.text`).
- Produces:
  - `is_verbatim_fragment(text: str, doc: Document, *, n: int = 8) -> bool` — True iff
    `text` has FEWER than `n` words AND its normalized form (lowercased,
    whitespace-collapsed) is a substring of some page's normalized text.
  - `assert_no_manuscript(text, doc, *, n=8, max_overlap=1)` extended: after the
    existing n-gram check, also `raise ManuscriptLeakError` if
    `is_verbatim_fragment(text, doc, n=n)` is True. Long text (≥ n words) keeps the
    n-gram-overlap behavior unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guard_shorttext.py
import pytest
from refereekit.guard import assert_no_manuscript, is_verbatim_fragment, ManuscriptLeakError

def test_short_verbatim_fragment_detected(real_doc):
    # a short (<8-word) phrase copied verbatim from page 1
    assert is_verbatim_fragment("prescribed degree-size sequences", real_doc) is True

def test_short_authored_note_not_flagged(real_doc):
    assert is_verbatim_fragment("PRX: lean accept-after-major", real_doc) is False

def test_assert_rejects_short_verbatim(real_doc):
    with pytest.raises(ManuscriptLeakError):
        assert_no_manuscript("prescribed degree-size sequences", real_doc)

def test_assert_allows_short_authored_note(real_doc):
    assert_no_manuscript("PRX: terse; reserve imperatives for real flaws", real_doc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_guard_shorttext.py -v`
Expected: FAIL — `is_verbatim_fragment` not defined; and `test_assert_rejects_short_verbatim` currently passes-through (short text → no n-grams → no raise).

- [ ] **Step 3: Write minimal implementation**

In `refereekit/guard.py`:
```python
def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def is_verbatim_fragment(text: str, doc: Document, *, n: int = 8) -> bool:
    words = re.findall(r"\w+", text)
    if len(words) >= n:
        return False
    norm = _normalize(text)
    if not norm:
        return False
    return any(norm in _normalize(p.text) for p in doc.pages)
```
Extend `assert_no_manuscript` — after the existing n-gram block, add:
```python
    if is_verbatim_fragment(text, doc, n=n):
        raise ManuscriptLeakError(
            f"input is a verbatim manuscript fragment (<{n} words)"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_guard_shorttext.py tests/test_guard.py -v`
Expected: PASS (new tests + existing guard tests still green).

- [ ] **Step 5: Commit**

```bash
git add refereekit/guard.py tests/test_guard_shorttext.py
git commit -m "feat: guard short-text verbatim-fragment check (closes <n-word gap)"
```

---

### Task 2: Memory schema — `created_at` column + migration

**Files:**
- Modify: `refereekit/memory.py`
- Test: `tests/test_memory_migration.py`

**Interfaces:**
- `Note` gains `created_at: str | None = None`.
- `SQLiteMemoryStore.__init__(path)`: `CREATE TABLE IF NOT EXISTS notes (text TEXT,
  venue TEXT, kind TEXT, created_at TEXT)`; then, if the table exists but lacks
  `created_at` (old SP-B DB), `ALTER TABLE notes ADD COLUMN created_at TEXT`. Detect
  via `PRAGMA table_info(notes)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_migration.py
import sqlite3
from refereekit.memory import SQLiteMemoryStore, Note

def test_opens_and_migrates_old_schema(tmp_path):
    db = tmp_path / "old.db"
    # simulate an SP-B-era DB with no created_at
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE notes (text TEXT, venue TEXT, kind TEXT)")
        c.execute("INSERT INTO notes VALUES ('old note','PRX','style')")
    m = SQLiteMemoryStore(db)  # must migrate, not crash
    cols = _columns(db)
    assert "created_at" in cols

def test_fresh_db_has_created_at(tmp_path):
    m = SQLiteMemoryStore(tmp_path / "new.db")
    assert "created_at" in _columns(tmp_path / "new.db")

def _columns(db):
    with sqlite3.connect(db) as c:
        return {r[1] for r in c.execute("PRAGMA table_info(notes)")}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_memory_migration.py -v`
Expected: FAIL — old-schema DB missing `created_at` after open (no migration yet).

- [ ] **Step 3: Write minimal implementation**

In `refereekit/memory.py`, update `Note` and `__init__`:
```python
@dataclass
class Note:
    text: str
    venue: str
    kind: str = "style"
    created_at: str | None = None

class SQLiteMemoryStore:
    def __init__(self, path: str | os.PathLike):
        self.path = str(path)
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS notes "
                      "(text TEXT, venue TEXT, kind TEXT, created_at TEXT)")
            cols = {r[1] for r in c.execute("PRAGMA table_info(notes)")}
            if "created_at" not in cols:
                c.execute("ALTER TABLE notes ADD COLUMN created_at TEXT")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_memory_migration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add refereekit/memory.py tests/test_memory_migration.py
git commit -m "feat: memory created_at column + migration for old DBs"
```

---

### Task 3: Guarded `store(note, doc)` — fail-closed

**Files:**
- Modify: `refereekit/memory.py`
- Test: `tests/test_memory.py` (update existing + add guarded cases)

**Interfaces:**
- Consumes: `refereekit.guard.assert_no_manuscript`, `refereekit.types.Document`.
- Produces: `SQLiteMemoryStore.store(note: Note, doc, *, created_at: str | None = None)
  -> None`:
  - if `doc is None`: `raise ValueError("store requires the session Document")`.
  - `guard.assert_no_manuscript(note.text, doc)` (raises `ManuscriptLeakError` on
    manuscript overlap).
  - insert `(text, venue, kind, created_at or note.created_at or <now ISO>)`.
  - The `MemoryStore` Protocol `store` signature updated to `store(note, doc, *,
    created_at=None)`.
- Note: `datetime` used only for the default timestamp; tests always pass an explicit
  `created_at` for determinism.

- [ ] **Step 1: Update the existing test + write new failing tests**

Rewrite `tests/test_memory.py` to the guarded signature (the old `store(Note(...))`
asserted the now-replaced unguarded behavior):

```python
# tests/test_memory.py
import pytest
from refereekit.memory import SQLiteMemoryStore, Note
from refereekit.guard import ManuscriptLeakError

def test_store_requires_doc(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    with pytest.raises(ValueError):
        m.store(Note("PRX: terse", "PRX"), None)   # no doc -> fail closed

def test_store_then_recall_by_venue(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    m.store(Note("PRX: terse; reserve imperatives for real flaws", "PRX"), real_doc,
            created_at="2026-01-01T00:00:00")
    m.store(Note("PRE: fuller discussion ok", "PRE"), real_doc,
            created_at="2026-01-02T00:00:00")
    prx = m.recall("PRX")
    assert len(prx) == 1 and prx[0].venue == "PRX"
    assert m.recall("NATURE") == []

def test_store_rejects_manuscript_text(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    with pytest.raises(ManuscriptLeakError):
        m.store(Note("prescribed degree-size sequences", "PRX"), real_doc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_memory.py -v`
Expected: FAIL — `store` doesn't take `doc`; guarded behavior not implemented.

- [ ] **Step 3: Write minimal implementation**

In `refereekit/memory.py` (add imports `from datetime import datetime, timezone`
and `from .guard import assert_no_manuscript`):
```python
    def store(self, note: Note, doc, *, created_at: str | None = None) -> None:
        if doc is None:
            raise ValueError("store requires the session Document")
        assert_no_manuscript(note.text, doc)
        ts = created_at or note.created_at or datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as c:
            c.execute("INSERT INTO notes (text, venue, kind, created_at) VALUES (?,?,?,?)",
                      (note.text, note.venue, note.kind, ts))
```
Update the `MemoryStore` Protocol `store` signature accordingly.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_memory.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add refereekit/memory.py tests/test_memory.py
git commit -m "feat: guarded memory store(note, doc) — fail-closed, timestamped"
```

---

### Task 4: `recall(venue, limit)` — dedup, recency, cap

**Files:**
- Modify: `refereekit/memory.py`
- Test: `tests/test_memory_recall.py`

**Interfaces:**
- `SQLiteMemoryStore.recall(venue: str, limit: int = 20) -> list[Note]`: distinct
  `text` for the venue, ordered by `created_at` DESC, at most `limit` rows. Returns
  `Note` objects (with their `created_at`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_recall.py
from refereekit.memory import SQLiteMemoryStore, Note

def test_recall_dedup_recency_cap(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    # duplicate text (older + newer) + a distinct newer note
    m.store(Note("dup note", "PRX"), real_doc, created_at="2026-01-01T00:00:00")
    m.store(Note("dup note", "PRX"), real_doc, created_at="2026-01-05T00:00:00")
    m.store(Note("newer distinct", "PRX"), real_doc, created_at="2026-01-09T00:00:00")
    got = m.recall("PRX")
    texts = [n.text for n in got]
    assert texts == ["newer distinct", "dup note"]   # distinct, newest-first
    assert len(got) == 2

def test_recall_respects_limit(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    for i in range(25):
        m.store(Note(f"note {i}", "PRX"), real_doc, created_at=f"2026-02-{i+1:02d}T00:00:00")
    assert len(m.recall("PRX", limit=10)) == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_memory_recall.py -v`
Expected: FAIL — current `recall` has no dedup/order/limit.

- [ ] **Step 3: Write minimal implementation**

Replace `recall` in `refereekit/memory.py`:
```python
    def recall(self, venue: str, limit: int = 20) -> list[Note]:
        with sqlite3.connect(self.path) as c:
            rows = c.execute(
                "SELECT text, kind, MAX(created_at) AS ca FROM notes "
                "WHERE venue=? GROUP BY text ORDER BY ca DESC LIMIT ?",
                (venue, limit),
            ).fetchall()
        return [Note(text=t, venue=venue, kind=k, created_at=ca) for (t, k, ca) in rows]
```
(GROUP BY text = dedup; MAX(created_at) = newest instance; ORDER/LIMIT = recency+cap.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_memory_recall.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add refereekit/memory.py tests/test_memory_recall.py
git commit -m "feat: recall dedup + recency + cap"
```

---

### Task 5: CLI `mem store` + `mem recall`

**Files:**
- Modify: `refereekit/cli.py`
- Test: `tests/test_cli_mem.py`

**Interfaces:**
- Consumes: `SQLiteMemoryStore`, `Note`, `Session`, `refereekit.guard.ManuscriptLeakError`.
- Produces: a `mem` subcommand with two forms (use a `--action` arg or nested choice;
  simplest: two subparsers `mem-store` / `mem-recall`, or a `mem` parser with a
  positional `action`). Implement as two subparsers for clarity:
  - `mem-store --session S --venue V --kind K --text "..." [--db PATH]`: loads
    `Session(S).load_doc()`, `store(Note(text,V,K), doc)` on a `SQLiteMemoryStore`
    (default db `<session>/memory.db`); prints confirmation; guard rejection or no
    doc → stderr + `return 2`.
  - `mem-recall --venue V [--db PATH] [--limit N]`: prints recalled notes.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_mem.py
from refereekit.cli import main
from refereekit.session import Session
from refereekit.ingest import ingest

def _sess(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "s"); s.save_doc(ingest(real_pdf_path)); return s

def test_mem_store_then_recall(tmp_path, real_pdf_path, capsys):
    s = _sess(tmp_path, real_pdf_path)
    db = str(s.dir / "memory.db")
    rc = main(["mem-store", "--session", str(s.dir), "--venue", "PRX",
               "--kind", "verdict", "--text", "PRX: lean accept-after-major", "--db", db])
    assert rc == 0
    rc2 = main(["mem-recall", "--venue", "PRX", "--db", db])
    out = capsys.readouterr().out
    assert rc2 == 0 and "accept-after-major" in out

def test_mem_store_rejects_manuscript(tmp_path, real_pdf_path, capsys):
    s = _sess(tmp_path, real_pdf_path)
    db = str(s.dir / "memory.db")
    rc = main(["mem-store", "--session", str(s.dir), "--venue", "PRX",
               "--kind", "quote", "--text", "prescribed degree-size sequences", "--db", db])
    assert rc == 2
    assert "manuscript" in capsys.readouterr().err.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli_mem.py -v`
Expected: FAIL — argparse: invalid choice `'mem-store'`.

- [ ] **Step 3: Write minimal implementation**

In `refereekit/cli.py`, register two subparsers and dispatch (import
`from .memory import SQLiteMemoryStore, Note`, `from .guard import ManuscriptLeakError`,
`from .session import Session`):
```python
    pms = sub.add_parser("mem-store")
    for a in ("--session", "--venue", "--kind", "--text"): pms.add_argument(a, required=True)
    pms.add_argument("--db")
    pmr = sub.add_parser("mem-recall")
    pmr.add_argument("--venue", required=True); pmr.add_argument("--db", required=True)
    pmr.add_argument("--limit", type=int, default=20)
    # dispatch:
    if args.cmd == "mem-store":
        s = Session(Path(args.session))
        db = args.db or str(s.dir / "memory.db")
        try:
            doc = s.load_doc()
            SQLiteMemoryStore(db).store(Note(args.text, args.venue, args.kind), doc)
        except (FileNotFoundError, ValueError, ManuscriptLeakError) as e:
            print(f"mem-store failed: {e}", file=sys.stderr); return 2
        print(f"stored note for {args.venue}"); return 0
    if args.cmd == "mem-recall":
        notes = SQLiteMemoryStore(args.db).recall(args.venue, args.limit)
        for nt in notes: print(f"[{nt.venue}/{nt.kind}] {nt.text}")
        return 0
```

- [ ] **Step 4: Run test to verify it passes, then full suite**

Run: `.venv/bin/pytest tests/test_cli_mem.py -v && .venv/bin/pytest -q`
Expected: target passes; whole suite green.

- [ ] **Step 5: Commit**

```bash
git add refereekit/cli.py tests/test_cli_mem.py
git commit -m "feat: CLI mem-store (guarded) + mem-recall"
```

---

### Task 6: Full suite + README + docs

**Files:**
- Modify: `README.md`
- Test: whole suite.

- [ ] **Step 1: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: ALL PASS. Report count.

- [ ] **Step 2: Manual smoke (fixture only, offline)**

```bash
.venv/bin/refereekit ingest tests/fixtures/real_paper.pdf --session /tmp/spc
.venv/bin/refereekit mem-store --session /tmp/spc --venue PRX --kind verdict --text "PRX: lean accept-after-major on approximate-but-validated theory" --db /tmp/spc/memory.db
.venv/bin/refereekit mem-recall --venue PRX --db /tmp/spc/memory.db
.venv/bin/refereekit mem-store --session /tmp/spc --venue PRX --kind quote --text "prescribed degree-size sequences" --db /tmp/spc/memory.db; echo "exit $? (expect 2)"
```
Expected: store OK; recall prints the note; manuscript-text store → exit 2.

- [ ] **Step 3: Update README**

Add a "Memory (SP-C)" section: `mem-store`/`mem-recall`, the guarded write
(manuscript text can never be stored; store requires the session doc), recall
dedup/recency/cap, and that notes are referee-authored (no auto-distillation).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: SP-C memory usage + confidentiality"
```

---

## Self-Review

**Spec coverage:**
- Guard short-text verbatim check (§3/§4) → Task 1 ✓ (resolves the carried guardrail)
- created_at + migration (§3/§4) → Task 2 ✓
- Guarded fail-closed `store(note, doc)` (§3/§4/§5) → Task 3 ✓
- recall dedup/recency/cap (§3/§4) → Task 4 ✓
- CLI (§4) → Task 5 ✓ — corrected: adds BOTH `mem-store` and `mem-recall` (no `mem`
  subcommand existed from SP-B; verified)
- Suite/README/docs (§7) → Task 6 ✓
- Deferred (not built): LLM auto-distillation, quote-match normalization, SP-D.

**Placeholder scan:** none — complete code + exact commands + verified fixture facts.

**Type consistency:** `Note(text, venue, kind, created_at=None)` used consistently;
`store(note, doc, *, created_at=None)` and `recall(venue, limit=20)` match across
memory + cli + tests; `is_verbatim_fragment(text, doc, *, n=8)` and the extended
`assert_no_manuscript` match Task 1 usage. `MemoryStore` Protocol updated once
(Task 3) to the new signatures.

**Confidentiality:** memory-write guarded + fail-closed; short-text gap closed;
tests assert manuscript text (verbatim phrase from the fixture) is rejected; only
referee-authored notes and the committed public fixtures are used.
