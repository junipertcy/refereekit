# refereekit SP-B (Phase 2) — Drafting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a voice-matched referee report and editor-response letter from fact-verified review content, via a zero-retention LLM client, without ever letting an unverified factual anchor land silently.

**Architecture:** Extend the SP-A package. Add `llm` (injectable backend, fail-closed on non-zero-retention), `memory` (read path behind a `MemoryStore` port with a SQLite adapter), a `records` addition to `session` that persists the verified-claim pool, and `drafts` (assemble prompt from pool + STYLE.md → LLM → re-extract & re-verify anchors → Draft with flags). Prose generation is LLM-driven; the fact guarantee is enforced deterministically after generation.

**Tech Stack:** Python 3.14, existing SP-A modules, stdlib (`sqlite3`, `json`, `re`), `pytest`. Real LLM backend uses the `anthropic` SDK behind an optional extra; tests use a `FakeBackend` — no network, no keys.

## Global Constraints

- **Confidentiality:** No confidential manuscript PDF/text and no manuscript identifier in any committed file, test, comment, or commit message. The only committable PDF is `tests/fixtures/sample_paper.pdf`. Manuscript text may travel only to the zero-retention LLM backend — never to memory or Exa.
- **STYLE.md only:** the referee's 5 past reports (confidential reviews of other manuscripts) are NEVER sent to the LLM and NEVER committed. Only the distilled `style/STYLE.md` is committed and used in prompts.
- **Fail closed:** `llm.complete` must refuse to send unless the backend reports `zero_retention is True`.
- **Anchor integrity:** no factual anchor reaches a draft's kept text unless it is in the verified pool AND re-verifies against the PDF; everything else becomes a visible flag.
- **Dependency-light core:** stdlib + PyMuPDF + pytest. The `anthropic` SDK is an OPTIONAL extra (`[llm]`), never imported at package import time or in tests.
- **Python:** target 3.14; run tools as `.venv/bin/python`, `.venv/bin/pytest`.
- **TDD:** every code change is preceded by a failing test. Commit after each green task. Tests are OFFLINE (no live API).

---

## File Structure

```
refereekit/
  llm.py                 Complete protocol, RetentionError, FakeBackend, complete(), AnthropicBackend
  memory.py              MemoryStore protocol, Note, SQLiteMemoryStore
  drafts.py              build_pool, report, editor_letter, anchor extraction + re-verify
  style.py               load_style(path)
  session.py             MODIFY: add record_claim() / verified_claims()
  cli.py                 MODIFY: add `draft` and `editor` subcommands
style/
  STYLE.md               distilled referee voice guide (committed; no raw reports)
tests/
  test_style.py
  test_llm.py
  test_memory.py
  test_session_records.py
  test_drafts_pool.py
  test_drafts_report.py
  test_drafts_editor.py
  test_cli_draft.py
pyproject.toml           MODIFY: add optional [llm] extra (anthropic)
```

---

### Task 1: Persist the verified-claim pool in the session

**Files:**
- Modify: `refereekit/session.py`
- Test: `tests/test_session_records.py`

**Interfaces:**
- Consumes: existing `Session` (`set_state`/`get_state`, attribute `dir`), `refereekit.types.Claim`.
- Produces:
  - `Session.record_claim(claim: Claim) -> None` — appends a verified claim to `state.json` under key `"claims"` (each stored as `{"text","kind","anchor"}`).
  - `Session.verified_claims() -> list[Claim]` — returns the recorded claims as `Claim` objects (empty list if none).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_session_records.py
from refereekit.session import Session
from refereekit.types import Claim

def test_record_and_read_back_claims(tmp_path):
    s = Session.create(tmp_path, "p")
    s.record_claim(Claim("prescribed degree-size sequences", "quote", "1"))
    s.record_claim(Claim("counting identity", "equation", "3"))
    got = Session(s.dir).verified_claims()
    assert [c.anchor for c in got] == ["1", "3"]
    assert got[0].kind == "quote" and got[0].text.startswith("prescribed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_session_records.py -v`
Expected: FAIL — `AttributeError: 'Session' object has no attribute 'record_claim'`

- [ ] **Step 3: Write minimal implementation**

Add to `refereekit/session.py` (import `Claim` at top: `from .types import Document, Claim`):

```python
    def record_claim(self, claim: Claim) -> None:
        claims = self.get_state("claims", [])
        claims.append({"text": claim.text, "kind": claim.kind, "anchor": claim.anchor})
        self.set_state("claims", claims)

    def verified_claims(self) -> list[Claim]:
        return [Claim(**c) for c in self.get_state("claims", [])]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_session_records.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refereekit/session.py tests/test_session_records.py
git commit -m "feat: persist verified-claim pool in session"
```

---

### Task 2: `style.load_style` + committed STYLE.md

**Files:**
- Create: `refereekit/style.py`, `style/STYLE.md`
- Test: `tests/test_style.py`

**Interfaces:**
- Produces: `load_style(path: str | Path) -> str` — returns the file's text; raises `FileNotFoundError` if absent.

**Note on STYLE.md content:** The controller authors `style/STYLE.md` by distilling the referee's voice from the 5 past reports (structure: `>`-prefixed sections; `*N*` numbered major issues; the phrase "The authors may consider…"; `_underscore_` emphasis; warm close; separate cover note). It contains ONLY voice rules and tiny anonymized snippets — NO raw report text, NO other-manuscript identifiers. The referee reviews it before commit.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_style.py
from pathlib import Path
from refereekit.style import load_style

def test_load_style_returns_guide_text():
    txt = load_style(Path("style/STYLE.md"))
    assert "The authors may consider" in txt   # a known voice marker
    assert len(txt) > 200

def test_load_style_missing_raises(tmp_path):
    try:
        load_style(tmp_path / "nope.md"); assert False
    except FileNotFoundError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_style.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.style'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/style.py
from pathlib import Path

def load_style(path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"style guide not found: {p}")
    return p.read_text()
```

Create `style/STYLE.md` with the distilled voice guide. Minimum content (the controller expands this from the 5 reports, keeping it anonymized):

```markdown
# Referee voice guide

Distilled writing conventions for referee reports. Voice rules only — no raw
report text, no manuscript identifiers.

## Structure
- Open by naming the submission and giving a one-paragraph plain summary.
- Group comments under `>`-prefixed headers: Overall / Major issues / Moderate /
  Organization / Minor.
- Number major issues `*1*`, `*2*`, … Reserve bare imperatives for genuine flaws;
  otherwise phrase asks as "The authors may consider…" or "It would be helpful if…".
- Emphasis via `_underscores_`. Close warmly.
- Editor letter is a SEPARATE short note; answer any editor questions in an
  a/b/c/d structure with a lead verdict word.

## Tone
- Skeptical but constructive; support gated on evidence.
- Cite specific locations (page / equation / figure) for every factual claim.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_style.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refereekit/style.py style/STYLE.md tests/test_style.py
git commit -m "feat: distilled STYLE.md voice guide + loader"
```

---

### Task 3: `llm` module — injectable backend, fail-closed

**Files:**
- Create: `refereekit/llm.py`
- Modify: `pyproject.toml` (add optional `[llm]` extra)
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces:
  - `class RetentionError(RuntimeError)`
  - `Complete` — a `typing.Protocol` with `zero_retention: bool` and `__call__(self, prompt: str) -> str`.
  - `class FakeBackend` — `__init__(self, canned, zero_retention=True)`; `canned` is `str` or `Callable[[str], str]`; `__call__` returns it; carries `zero_retention`.
  - `complete(prompt: str, *, backend: Complete, manuscript_ok: bool = False) -> str` — raises `RetentionError` unless `getattr(backend, "zero_retention", False) is True`; otherwise returns `backend(prompt)`.
  - `class AnthropicBackend` — thin real backend; `zero_retention` set from explicit constructor arg (caller asserts their account terms); calls the `anthropic` SDK. Imported lazily inside `__init__` so the package imports without the SDK. NOT unit-tested against the network.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm.py
import pytest
from refereekit.llm import complete, FakeBackend, RetentionError

def test_zero_retention_backend_returns_text():
    b = FakeBackend("hello draft", zero_retention=True)
    assert complete("prompt", backend=b, manuscript_ok=True) == "hello draft"

def test_non_zero_retention_fails_closed():
    b = FakeBackend("should not send", zero_retention=False)
    with pytest.raises(RetentionError):
        complete("prompt", backend=b, manuscript_ok=True)

def test_callable_canned_receives_prompt():
    b = FakeBackend(lambda p: f"echo:{p}", zero_retention=True)
    assert complete("XYZ", backend=b) == "echo:XYZ"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.llm'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/llm.py
from typing import Protocol, Callable, Union, runtime_checkable

class RetentionError(RuntimeError):
    pass

@runtime_checkable
class Complete(Protocol):
    zero_retention: bool
    def __call__(self, prompt: str) -> str: ...

class FakeBackend:
    def __init__(self, canned: Union[str, Callable[[str], str]], zero_retention: bool = True):
        self._canned = canned
        self.zero_retention = zero_retention
    def __call__(self, prompt: str) -> str:
        return self._canned(prompt) if callable(self._canned) else self._canned

def complete(prompt: str, *, backend, manuscript_ok: bool = False) -> str:
    if getattr(backend, "zero_retention", False) is not True:
        raise RetentionError(
            "refusing to send: backend is not marked zero_retention"
        )
    return backend(prompt)

class AnthropicBackend:
    """Thin real backend. Not unit-tested against the network."""
    def __init__(self, model: str, zero_retention: bool, api_key: str | None = None):
        import anthropic  # lazy: package imports without the SDK
        self.zero_retention = zero_retention
        self._model = model
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    def __call__(self, prompt: str) -> str:
        msg = self._client.messages.create(
            model=self._model, max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
```

Add to `pyproject.toml` under `[project.optional-dependencies]`:

```toml
llm = ["anthropic>=0.40"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add refereekit/llm.py pyproject.toml tests/test_llm.py
git commit -m "feat: zero-retention LLM client (fail-closed, injectable backend)"
```

---

### Task 4: `memory` read path — MemoryStore port + SQLite adapter

**Files:**
- Create: `refereekit/memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Consumes: `refereekit.guard.assert_no_manuscript`, `refereekit.types.Document` (for the guard test).
- Produces:
  - `Note` dataclass: `text: str`, `venue: str`, `kind: str = "style"`.
  - `MemoryStore` — `Protocol` with `recall(self, venue: str) -> list[Note]` and `store(self, note: Note) -> None`.
  - `SQLiteMemoryStore` — `__init__(self, path)` (creates a `notes(text, venue, kind)` table); `store(note)` inserts; `recall(venue)` returns notes for that venue as `Note` objects.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py
from refereekit.memory import SQLiteMemoryStore, Note

def test_store_then_recall_by_venue(tmp_path):
    m = SQLiteMemoryStore(tmp_path / "mem.db")
    m.store(Note(text="PRX: terse; reserve imperatives for real flaws", venue="PRX"))
    m.store(Note(text="PRE: fuller discussion ok", venue="PRE"))
    prx = m.recall("PRX")
    assert len(prx) == 1 and prx[0].venue == "PRX"
    assert m.recall("NATURE") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_memory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.memory'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/memory.py
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

@dataclass
class Note:
    text: str
    venue: str
    kind: str = "style"

class MemoryStore(Protocol):
    def recall(self, venue: str) -> list["Note"]: ...
    def store(self, note: "Note") -> None: ...

class SQLiteMemoryStore:
    def __init__(self, path):
        self.path = str(path)
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS notes (text TEXT, venue TEXT, kind TEXT)")

    def store(self, note: Note) -> None:
        with sqlite3.connect(self.path) as c:
            c.execute("INSERT INTO notes (text, venue, kind) VALUES (?,?,?)",
                      (note.text, note.venue, note.kind))

    def recall(self, venue: str) -> list[Note]:
        with sqlite3.connect(self.path) as c:
            rows = c.execute("SELECT text, venue, kind FROM notes WHERE venue=?",
                             (venue,)).fetchall()
        return [Note(text=t, venue=v, kind=k) for (t, v, k) in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_memory.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refereekit/memory.py tests/test_memory.py
git commit -m "feat: memory read path (MemoryStore port + SQLite adapter)"
```

---

### Task 5: `drafts.build_pool` + anchor extraction helper

**Files:**
- Create: `refereekit/drafts.py`
- Test: `tests/test_drafts_pool.py`

**Interfaces:**
- Consumes: `Session.verified_claims()`, `Session.get_state`, `refereekit.types.Claim`.
- Produces:
  - `build_pool(session) -> dict` — returns `{"claims": list[Claim], "verdict": dict}` where verdict is `session.get_state("verdict", {})`.
  - `extract_anchors(text: str) -> list[Claim]` — parses inline citations of two forms from prose: `p. N` / `page N` → `Claim(text="", kind="page", anchor="N")`, and `Eq. (N)` / `equation (N)` → `Claim(text="", kind="equation", anchor="N")`. Returns one Claim per citation found (deduped by (kind, anchor)).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_drafts_pool.py
from refereekit.drafts import build_pool, extract_anchors
from refereekit.session import Session
from refereekit.types import Claim

def test_build_pool_gathers_claims_and_verdict(tmp_path):
    s = Session.create(tmp_path, "p")
    s.record_claim(Claim("counting identity", "equation", "3"))
    s.set_state("verdict", {"recommend": "major"})
    pool = build_pool(s)
    assert pool["verdict"]["recommend"] == "major"
    assert pool["claims"][0].anchor == "3"

def test_extract_anchors_finds_page_and_equation():
    text = "As shown on p. 16 and in Eq. (3), the result holds."
    got = {(c.kind, c.anchor) for c in extract_anchors(text)}
    assert ("page", "16") in got
    assert ("equation", "3") in got

def test_extract_anchors_dedupes():
    text = "Eq. (3) ... again Eq. (3)."
    assert len(extract_anchors(text)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_drafts_pool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.drafts'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/drafts.py
import re
from .types import Claim

_PAGE = re.compile(r"(?:\bp\.?\s*|\bpage\s+)(\d{1,3})\b", re.I)
_EQ = re.compile(r"(?:\bEq\.?\s*|\bequation\s+)\((\d{1,3})\)", re.I)

def extract_anchors(text: str) -> list[Claim]:
    found = {}
    for m in _PAGE.finditer(text):
        found[("page", m.group(1))] = Claim("", "page", m.group(1))
    for m in _EQ.finditer(text):
        found[("equation", m.group(1))] = Claim("", "equation", m.group(1))
    return list(found.values())

def build_pool(session) -> dict:
    return {"claims": session.verified_claims(),
            "verdict": session.get_state("verdict", {})}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_drafts_pool.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add refereekit/drafts.py tests/test_drafts_pool.py
git commit -m "feat: drafts pool builder + anchor extraction"
```

---

### Task 6: `drafts.report` — generate + re-verify → Draft with flags

**Files:**
- Modify: `refereekit/drafts.py`
- Test: `tests/test_drafts_report.py`

**Interfaces:**
- Consumes: `build_pool`, `extract_anchors`, `refereekit.verify.verify`, `refereekit.llm.complete`, `refereekit.style.load_style`, `Session.load_doc()`, `refereekit.types.Claim/Verdict`.
- Produces:
  - `Draft` dataclass: `text: str`, `flags: list`.
  - `Flag` dataclass: `anchor: str`, `kind: str`, `reason: str`.
  - `build_prompt(pool: dict, style: str, section_lengths: dict) -> str` — assembles the drafting prompt: includes the style guide text, the verdict, and a rendered list of the pool's claims; instructs the model to cite only anchors present in the pool.
  - `report(session, verdict: dict, section_lengths: dict, *, backend, style_path) -> Draft` — builds pool, builds prompt, calls `llm.complete(prompt, backend=backend, manuscript_ok=True)`, extracts anchors from the returned prose, and for each: keep if it matches a pool claim's (kind, anchor) AND `verify` returns PASS; else record a `Flag`. Returns `Draft(text=<prose>, flags=[...])`. Empty pool → still generates (prompt notes no verified content), but any cited anchor will be flagged as out-of-pool.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_drafts_report.py
from refereekit.drafts import report, Draft
from refereekit.llm import FakeBackend
from refereekit.session import Session
from refereekit.types import Claim
from refereekit.ingest import ingest

def _session_with_pool(tmp_path, sample_pdf_path):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(sample_pdf_path))
    s.record_claim(Claim("counting identity", "equation", "3"))  # exists in fixture
    s.set_state("verdict", {"recommend": "minor"})
    return s

def test_report_keeps_valid_and_flags_invalid(tmp_path, sample_pdf_path):
    s = _session_with_pool(tmp_path, sample_pdf_path)
    # canned prose: one in-pool+valid anchor (Eq 3), one out-of-pool (Eq 9, also absent from PDF)
    canned = "The identity in Eq. (3) is correct. However Eq. (9) is unsupported."
    d = report(s, s.get_state("verdict"), {}, backend=FakeBackend(canned), style_path="style/STYLE.md")
    assert isinstance(d, Draft)
    assert d.text == canned
    flagged = {(f.kind, f.anchor) for f in d.flags}
    assert ("equation", "9") in flagged      # out-of-pool AND fails verify -> flagged
    assert ("equation", "3") not in flagged   # in pool AND verifies -> kept

def test_prompt_contains_style_and_pool(tmp_path, sample_pdf_path):
    s = _session_with_pool(tmp_path, sample_pdf_path)
    seen = {}
    def capture(p): seen["p"] = p; return "ok"
    report(s, s.get_state("verdict"), {}, backend=FakeBackend(capture), style_path="style/STYLE.md")
    assert "The authors may consider" in seen["p"]   # STYLE.md content present
    assert "3" in seen["p"]                            # pool claim anchor present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_drafts_report.py -v`
Expected: FAIL — `ImportError: cannot import name 'report'` (or `Draft`)

- [ ] **Step 3: Write minimal implementation**

Add to `refereekit/drafts.py` (extend imports: `from dataclasses import dataclass, field`; `from .verify import verify`; `from .llm import complete`; `from .style import load_style`):

```python
@dataclass
class Flag:
    anchor: str
    kind: str
    reason: str

@dataclass
class Draft:
    text: str
    flags: list = field(default_factory=list)

def build_prompt(pool: dict, style: str, section_lengths: dict) -> str:
    claim_lines = "\n".join(
        f"- {c.kind} ({c.anchor}): {c.text}" for c in pool["claims"]
    ) or "(no verified claims available)"
    lengths = ", ".join(f"{k}={v}" for k, v in section_lengths.items()) or "default"
    return (
        "Write a referee report in the voice described below.\n\n"
        f"=== VOICE GUIDE ===\n{style}\n\n"
        f"=== VERDICT ===\n{pool['verdict']}\n\n"
        f"=== VERIFIED CLAIMS (cite ONLY these anchors) ===\n{claim_lines}\n\n"
        f"=== SECTION LENGTHS ===\n{lengths}\n\n"
        "Cite page/equation anchors only if they appear in the verified claims above."
    )

def report(session, verdict: dict, section_lengths: dict, *, backend, style_path) -> Draft:
    pool = build_pool(session)
    prompt = build_prompt(pool, load_style(style_path), section_lengths)
    prose = complete(prompt, backend=backend, manuscript_ok=True)
    doc = session.load_doc()
    pool_keys = {(c.kind, c.anchor) for c in pool["claims"]}
    flags = []
    for a in extract_anchors(prose):
        if (a.kind, a.anchor) not in pool_keys:
            flags.append(Flag(a.anchor, a.kind, "not in verified pool"))
        elif verify(a, doc).status != "PASS":
            flags.append(Flag(a.anchor, a.kind, "failed re-verification"))
    return Draft(text=prose, flags=flags)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_drafts_report.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add refereekit/drafts.py tests/test_drafts_report.py
git commit -m "feat: drafts.report with verified-pool re-verification and flags"
```

---

### Task 7: `drafts.editor_letter` — a/b/c/d structure, same pipeline

**Files:**
- Modify: `refereekit/drafts.py`
- Test: `tests/test_drafts_editor.py`

**Interfaces:**
- Consumes: same as Task 6.
- Produces:
  - `editor_letter(session, answers: dict, *, backend, style_path) -> Draft` — like `report`, but `build_prompt` is replaced by an editor-letter prompt that includes the `answers` dict (keyed a/b/c/d) and instructs a short structured letter with a lead verdict word per item. Same extract + re-verify → flags pipeline.
  - `build_editor_prompt(pool: dict, style: str, answers: dict) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_drafts_editor.py
from refereekit.drafts import editor_letter, Draft
from refereekit.llm import FakeBackend
from refereekit.session import Session
from refereekit.types import Claim
from refereekit.ingest import ingest

def test_editor_letter_runs_pipeline_and_flags(tmp_path, sample_pdf_path):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(sample_pdf_path))
    s.record_claim(Claim("counting identity", "equation", "3"))
    canned = "a) Novelty: PARTLY. See Eq. (9) which is not in the paper."
    d = editor_letter(s, {"a": "novelty?"}, backend=FakeBackend(canned), style_path="style/STYLE.md")
    assert isinstance(d, Draft) and d.text == canned
    assert ("equation", "9") in {(f.kind, f.anchor) for f in d.flags}

def test_editor_prompt_includes_answers(tmp_path, sample_pdf_path):
    s = Session.create(tmp_path, "p"); s.save_doc(ingest(sample_pdf_path))
    seen = {}
    def cap(p): seen["p"] = p; return "ok"
    editor_letter(s, {"c": "impact question"}, backend=FakeBackend(cap), style_path="style/STYLE.md")
    assert "impact question" in seen["p"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_drafts_editor.py -v`
Expected: FAIL — `ImportError: cannot import name 'editor_letter'`

- [ ] **Step 3: Write minimal implementation**

Add to `refereekit/drafts.py`:

```python
def build_editor_prompt(pool: dict, style: str, answers: dict) -> str:
    ans = "\n".join(f"{k}) {v}" for k, v in answers.items()) or "(no questions)"
    claim_lines = "\n".join(
        f"- {c.kind} ({c.anchor}): {c.text}" for c in pool["claims"]
    ) or "(no verified claims available)"
    return (
        "Write a SHORT editor-response letter in the voice described below. "
        "Answer each item with a lead verdict word, in a/b/c/d structure.\n\n"
        f"=== VOICE GUIDE ===\n{style}\n\n"
        f"=== EDITOR QUESTIONS / YOUR ANSWERS ===\n{ans}\n\n"
        f"=== VERIFIED CLAIMS (cite ONLY these) ===\n{claim_lines}\n"
    )

def editor_letter(session, answers: dict, *, backend, style_path) -> Draft:
    pool = build_pool(session)
    prompt = build_editor_prompt(pool, load_style(style_path), answers)
    prose = complete(prompt, backend=backend, manuscript_ok=True)
    doc = session.load_doc()
    pool_keys = {(c.kind, c.anchor) for c in pool["claims"]}
    flags = []
    for a in extract_anchors(prose):
        if (a.kind, a.anchor) not in pool_keys:
            flags.append(Flag(a.anchor, a.kind, "not in verified pool"))
        elif verify(a, doc).status != "PASS":
            flags.append(Flag(a.anchor, a.kind, "failed re-verification"))
    return Draft(text=prose, flags=flags)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_drafts_editor.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add refereekit/drafts.py tests/test_drafts_editor.py
git commit -m "feat: drafts.editor_letter (a/b/c/d, same re-verify pipeline)"
```

---

### Task 8: CLI `draft` + `editor`, full suite, README, acceptance

**Files:**
- Modify: `refereekit/cli.py`, `README.md`
- Test: `tests/test_cli_draft.py`

**Interfaces:**
- Consumes: `drafts.report`, `drafts.editor_letter`, `refereekit.llm.FakeBackend` (test only), `Session`.
- Produces: two subcommands. To keep the suite offline and key-free, the CLI selects its backend from an env var: if `REFEREEKIT_FAKE=1`, it uses `FakeBackend(os.environ.get("REFEREEKIT_FAKE_TEXT", "draft"))`; otherwise it constructs `AnthropicBackend` from `REFEREEKIT_MODEL` + `REFEREEKIT_ZERO_RETENTION=1`. Writes the draft text to `session/drafts/report.txt` (or `editor.txt`) and prints a summary incl. flag count; returns 0.
  - `draft --session <dir> [--length <sec=val> ...]`
  - `editor --session <dir> --answers <k=v> [...]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_draft.py
import os
from refereekit.cli import main
from refereekit.session import Session
from refereekit.types import Claim
from refereekit.ingest import ingest

def test_cli_draft_writes_report_offline(tmp_path, sample_pdf_path, capsys, monkeypatch):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(sample_pdf_path))
    s.record_claim(Claim("counting identity", "equation", "3"))
    s.set_state("verdict", {"recommend": "minor"})
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Eq. (3) is fine.")
    rc = main(["draft", "--session", str(s.dir)])
    assert rc == 0
    assert (s.dir / "drafts" / "report.txt").read_text() == "Eq. (3) is fine."
    assert "flag" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli_draft.py -v`
Expected: FAIL — argparse: invalid choice `'draft'`

- [ ] **Step 3: Write minimal implementation**

Add a backend selector and two subcommands to `refereekit/cli.py` (add `import os`; import `drafts`, `FakeBackend`, `AnthropicBackend`):

```python
def _backend():
    import os
    from .llm import FakeBackend
    if os.environ.get("REFEREEKIT_FAKE") == "1":
        return FakeBackend(os.environ.get("REFEREEKIT_FAKE_TEXT", "draft"))
    from .llm import AnthropicBackend
    return AnthropicBackend(
        model=os.environ.get("REFEREEKIT_MODEL", "claude-opus-4-8"),
        zero_retention=os.environ.get("REFEREEKIT_ZERO_RETENTION") == "1",
    )

def _write_draft(session, name, draft):
    d = session.dir / "drafts"; d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.txt").write_text(draft.text)
    print(f"{name}: wrote {len(draft.text)} chars, {len(draft.flags)} flag(s)")
    for f in draft.flags:
        print(f"  FLAG {f.kind} ({f.anchor}): {f.reason}")
```

In `main`, register subcommands and dispatch:

```python
    pd = sub.add_parser("draft"); pd.add_argument("--session", required=True)
    pd.add_argument("--length", action="append", default=[])
    pe = sub.add_parser("editor"); pe.add_argument("--session", required=True)
    pe.add_argument("--answers", action="append", default=[])
    # ... in dispatch:
    if args.cmd == "draft":
        from . import drafts
        s = Session(Path(args.session))
        lengths = dict(x.split("=", 1) for x in args.length)
        d = drafts.report(s, s.get_state("verdict", {}), lengths,
                          backend=_backend(), style_path="style/STYLE.md")
        _write_draft(s, "report", d); return 0
    if args.cmd == "editor":
        from . import drafts
        s = Session(Path(args.session))
        answers = dict(x.split("=", 1) for x in args.answers)
        d = drafts.editor_letter(s, answers, backend=_backend(), style_path="style/STYLE.md")
        _write_draft(s, "editor", d); return 0
```

- [ ] **Step 4: Run test to verify it passes, then the full suite**

Run: `.venv/bin/pytest tests/test_cli_draft.py -v && .venv/bin/pytest -q`
Expected: target test PASSES; whole suite (SP-A + SP-B) all green.

- [ ] **Step 5: Manual acceptance (documented; fixture only, real API)**

Only if the referee has confirmed zero-retention terms. Against the FIXTURE:
```bash
export REFEREEKIT_ZERO_RETENTION=1 REFEREEKIT_MODEL=claude-opus-4-8
.venv/bin/refereekit ingest tests/fixtures/sample_paper.pdf --session /tmp/demo-b
.venv/bin/refereekit draft --session /tmp/demo-b
```
Expected: writes `/tmp/demo-b/drafts/report.txt`; prints flag count. (Do NOT run against a confidential manuscript in a shared shell history.)

- [ ] **Step 6: Update README + commit**

Add an SP-B section to `README.md` documenting `draft`/`editor`, the env-var backend selection, and the confidentiality note (manuscript text → zero-retention LLM only; STYLE.md not raw reports). Then:

```bash
git add refereekit/cli.py tests/test_cli_draft.py README.md
git commit -m "feat: CLI draft + editor subcommands; SP-B docs"
```

---

## Self-Review

**Spec coverage (SP-B):**
- `llm` fail-closed + injectable backend (§4) → Task 3 ✓
- `drafts` verified-pool + post-gen re-verify → flags (§3, §4) → Tasks 5–7 ✓ (the guarantee test is Task 6 Step 1)
- `memory` read path, MemoryStore port + SQLite (§4) → Task 4 ✓
- distilled `STYLE.md`, raw reports never sent/committed (§3) → Task 2 ✓ (+ Global Constraints)
- verified-claim pool persisted in session (implied by build_pool; not in SP-A) → Task 1 ✓ (gap found and covered)
- CLI surface + offline tests + manual real-API acceptance (§7) → Task 8 ✓
- per-section length param on report; choosing stays in driver (§3) → Task 6/8 (`section_lengths` / `--length`) ✓
- Deferred correctly (not in SP-B): memory write/recall accumulation (SP-C), litsearch, embedded loop (SP-D).

**Placeholder scan:** none — every step has complete code and exact commands.

**Type consistency:** `Complete`/`FakeBackend`/`complete(...)` used identically Tasks 3→6→7→8; `Draft{text,flags}` / `Flag{anchor,kind,reason}` defined Task 6, reused Task 7/8; `Note`/`SQLiteMemoryStore` Task 4; `build_pool`/`extract_anchors` Task 5 reused in 6/7; `Session.record_claim`/`verified_claims` Task 1 reused in 5/6. `verify(Claim, Document).status` matches the SP-A signature verified in the repo.

**Confidentiality check:** the only committable PDF remains the fixture; STYLE.md carries no raw-report text; manuscript text routes only through `llm`; `memory.recall` takes a venue string, not manuscript text; the real backend is an optional extra imported lazily so tests never touch the network.
