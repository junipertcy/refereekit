# refereekit SP-D (Phase 4) — Embedded Review Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** `refereekit review <pdf>` drives a complete review in one process (ingest → summarize → Q&A REPL → verdict gate → draft → detail gate → editor) with no external harness — fully standalone.

**Architecture:** New `refereekit/agent/` package with a scripted orchestrator `run_review`. Deterministic control flow; the LLM only fills prose within steps. Injectable `input_fn`/`output_fn` make the REPL + gates testable offline. Multi-turn via a running transcript rebuilt into each prompt — `llm` is unchanged (single audited zero-retention egress path). Reuses ingest, verify, render, drafts, session, memory, guard — no new domain logic.

**Tech Stack:** Python 3.14, stdlib, PyMuPDF, pytest. No new deps. No live API in tests (FakeBackend + scripted I/O).

## Global Constraints

- **Confidentiality:** manuscript text flows ONLY to `llm.complete` (zero-retention, unchanged) and the git-ignored session dir (the transcript). The loop never writes manuscript text to memory or Exa; memory recall is read-only into the prompt.
- **Scripted, not autonomous:** the pipeline sequence is hardcoded; the LLM never chooses which tool runs.
- **Anchor integrity:** Q&A answers' anchors are re-verified against the doc; unverified anchors are flagged, never shown as confirmed.
- **Dependency-light:** stdlib + existing modules only. No change to `llm`/`guard`/`verify`/`ingest`/`session`/`memory`/`drafts` signatures — SP-D orchestrates them.
- **Offline tests:** `input_fn`/`output_fn` injected; `FakeBackend`; fixture `real_paper.pdf`. No network/live LLM in the suite.
- **Python:** target 3.14; run tools as `.venv/bin/python`, `.venv/bin/pytest`.
- **TDD:** failing test first; commit per task.

## Verified interfaces (from the current tree)

- `Session.create(base, name)`, `.save_doc(doc)`, `.load_doc()`, `.set_state(k,v)`, `.get_state(k,default)`, `.record_claim(Claim)`.
- `drafts.extract_anchors(text) -> list[Claim]`; `verify.verify(Claim, doc) -> Verdict` (`.status` in PASS/FAIL/FLAG).
- `render.init_page(session, title)`, `render.append_qa(session, q, answer_html)`.
- `drafts.report(session, verdict, section_lengths, *, backend, style_path, memory=None, venue=None) -> Draft`; `drafts.editor_letter(session, answers, *, backend, style_path, memory=None, venue=None) -> Draft`; `Draft(text, flags)`.
- `llm.complete(prompt, *, backend, manuscript_ok=False)`; `FakeBackend(canned, zero_retention=True)`; cli `_backend()` env pattern.
- `SQLiteMemoryStore(path)`; git-ignores already cover `work/` and repo-root artifacts.

---

### Task 1: Prompt context assembly (`_doc_context`) — pure, tested first

**Files:**
- Create: `refereekit/agent/__init__.py`, `refereekit/agent/loop.py`
- Test: `tests/test_agent_context.py`

**Interfaces:**
- Produces: `_doc_context(doc, transcript, question, *, max_pages=None) -> str` —
  assembles a bounded prompt string from: a doc digest (page texts, optionally
  truncated), the running `transcript` (list of `(q, a)` tuples), and the new
  `question`. Pure function, no I/O, no LLM. Deterministic.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_context.py
from refereekit.agent.loop import _doc_context
from refereekit.types import Document, Page

def _doc():
    return Document(pages=[Page(1, "alpha beta gamma", []), Page(2, "delta epsilon", [])],
                    figures=[], equations=[], sections=[])

def test_context_includes_doc_transcript_and_question():
    ctx = _doc_context(_doc(), [("prior q", "prior a")], "new question?")
    assert "alpha beta" in ctx           # doc content present
    assert "prior q" in ctx and "prior a" in ctx   # transcript present
    assert "new question?" in ctx        # current question present

def test_context_empty_transcript_ok():
    ctx = _doc_context(_doc(), [], "q1")
    assert "q1" in ctx and "alpha" in ctx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent_context.py -v`
Expected: FAIL — `refereekit.agent` module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/agent/__init__.py
from .loop import run_review, ReviewResult
```
```python
# refereekit/agent/loop.py
def _doc_context(doc, transcript, question, *, max_pages=None) -> str:
    pages = doc.pages if max_pages is None else doc.pages[:max_pages]
    doc_text = "\n".join(f"[page {p.n}]\n{p.text}" for p in pages)
    convo = "\n".join(f"Q: {q}\nA: {a}" for (q, a) in transcript)
    parts = [
        "=== PAPER (verify every citation against this) ===",
        doc_text,
    ]
    if convo:
        parts += ["=== PRIOR Q&A ===", convo]
    parts += ["=== QUESTION ===", question,
              "Answer concisely. Cite pages as 'p. N' and equations as 'Eq. (N)'."]
    return "\n\n".join(parts)
```
(`run_review`/`ReviewResult` are added in Task 4; to keep `__init__` importable now,
temporarily also define stubs OR import lazily. Simplest: in Task 1, make
`refereekit/agent/__init__.py` empty and import `_doc_context` from
`refereekit.agent.loop` in the test. Replace `__init__.py` exports in Task 4.)

**Correction for Step 3:** leave `refereekit/agent/__init__.py` EMPTY in Task 1
(the test imports from `refereekit.agent.loop` directly). Task 4 adds the exports.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_agent_context.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add refereekit/agent/__init__.py refereekit/agent/loop.py tests/test_agent_context.py
git commit -m "feat: agent loop prompt-context assembly"
```

---

### Task 2: Q&A REPL step — injectable I/O, verify, record, render

**Files:**
- Modify: `refereekit/agent/loop.py`
- Test: `tests/test_agent_qa.py`

**Interfaces:**
- Consumes: `_doc_context`, `llm.complete`, `drafts.extract_anchors`, `verify.verify`,
  `render.init_page`/`append_qa`, `Session`, `Claim`.
- Produces: `_qa_loop(session, doc, *, backend, input_fn, output_fn, sentinel="") ->
  list[tuple]` — returns the transcript. Behavior per iteration:
  - `q = input_fn("question> ")`; if `q.strip() == sentinel` → break.
  - `prompt = _doc_context(doc, transcript, q)`;
    `ans = complete(prompt, backend=backend, manuscript_ok=True)`.
  - for each `a in extract_anchors(ans)`: if `verify(a, doc).status == "PASS"`:
    `session.record_claim(a)` (so the later draft pool contains it); else collect a
    flag note.
  - `render.append_qa(session, q, ans + <flag suffix if any>)`; `output_fn(ans)` (and
    output a flag warning if any anchor failed).
  - append `(q, ans)` to transcript.
  - `render.init_page(session, "Review")` is called ONCE before the loop.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_qa.py
from refereekit.agent.loop import _qa_loop
from refereekit.session import Session
from refereekit.ingest import ingest
from refereekit.llm import FakeBackend

def test_qa_records_verified_anchor_and_appends_html(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "p"); doc = ingest(real_pdf_path); s.save_doc(doc)
    # canned answer cites a real equation (3 exists) and a bogus one (99)
    canned = "The identity in Eq. (3) holds; Eq. (99) does not."
    out = []
    script = iter(["what is the key result?", ""])   # one question then sentinel
    tr = _qa_loop(s, doc, backend=FakeBackend(canned),
                  input_fn=lambda _="": next(script), output_fn=out.append)
    assert len(tr) == 1 and tr[0][0] == "what is the key result?"
    # verified anchor recorded to session pool; bogus one not
    anchors = {(c.kind, c.anchor) for c in Session(s.dir).verified_claims()}
    assert ("equation", "3") in anchors
    assert ("equation", "99") not in anchors
    assert (s.dir / "index.html").exists()   # render wrote the page
    assert any("Eq. (3)" in o for o in out)  # answer emitted

def test_qa_sentinel_first_yields_empty_transcript(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "p"); doc = ingest(real_pdf_path); s.save_doc(doc)
    tr = _qa_loop(s, doc, backend=FakeBackend("x"),
                  input_fn=lambda _="": "", output_fn=lambda _:None)
    assert tr == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent_qa.py -v`
Expected: FAIL — `_qa_loop` not defined.

- [ ] **Step 3: Write minimal implementation**

Add to `refereekit/agent/loop.py` (imports: `from ..llm import complete`;
`from ..drafts import extract_anchors`; `from ..verify import verify`;
`from .. import render`):
```python
def _qa_loop(session, doc, *, backend, input_fn, output_fn, sentinel="") -> list:
    render.init_page(session, "Review")
    transcript = []
    while True:
        q = input_fn("question> ")
        if q.strip() == sentinel:
            break
        prompt = _doc_context(doc, transcript, q)
        ans = complete(prompt, backend=backend, manuscript_ok=True)
        flags = []
        for a in extract_anchors(ans):
            if verify(a, doc).status == "PASS":
                session.record_claim(a)
            else:
                flags.append(f"{a.kind} ({a.anchor})")
        suffix = f"\n[UNVERIFIED: {', '.join(flags)}]" if flags else ""
        render.append_qa(session, q, f"<p>{ans}{suffix}</p>")
        output_fn(ans + (f"  ⚠ unverified: {', '.join(flags)}" if flags else ""))
        transcript.append((q, ans))
    return transcript
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_agent_qa.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add refereekit/agent/loop.py tests/test_agent_qa.py
git commit -m "feat: agent Q&A REPL step (injectable IO, verify+record, render)"
```

---

### Task 3: Human gates — verdict + section lengths via input_fn

**Files:**
- Modify: `refereekit/agent/loop.py`
- Test: `tests/test_agent_gates.py`

**Interfaces:**
- Produces:
  - `_verdict_gate(session, *, input_fn, output_fn) -> dict` — prompts for
    `recommend`, `venue`, `major_minor`; stores `{"recommend","venue","major_minor"}`
    to `session.set_state("verdict", ...)`; returns it.
  - `_detail_gate(*, input_fn) -> dict` — prompts for a comma-separated
    `section=length` list (blank → `{}`); returns a `section_lengths` dict.
  - `_editor_answers(*, input_fn) -> dict` — prompts for a/b/c/d answers (blank
    key ends); returns the answers dict (may be empty).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_gates.py
from refereekit.agent.loop import _verdict_gate, _detail_gate, _editor_answers
from refereekit.session import Session

def test_verdict_gate_records_state(tmp_path):
    s = Session.create(tmp_path, "p")
    script = iter(["major revision", "PRX", "major"])
    v = _verdict_gate(s, input_fn=lambda _="": next(script), output_fn=lambda _:None)
    assert v["recommend"] == "major revision" and v["venue"] == "PRX"
    assert Session(s.dir).get_state("verdict")["venue"] == "PRX"

def test_detail_gate_parses_lengths():
    script = iter(["major=short, minor=medium"])
    d = _detail_gate(input_fn=lambda _="": next(script))
    assert d == {"major": "short", "minor": "medium"}

def test_detail_gate_blank_is_default():
    assert _detail_gate(input_fn=lambda _="": "") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent_gates.py -v`
Expected: FAIL — gate functions not defined.

- [ ] **Step 3: Write minimal implementation**

```python
def _verdict_gate(session, *, input_fn, output_fn) -> dict:
    v = {"recommend": input_fn("verdict (recommend)> ").strip(),
         "venue": input_fn("venue> ").strip(),
         "major_minor": input_fn("major/minor> ").strip()}
    session.set_state("verdict", v)
    return v

def _detail_gate(*, input_fn) -> dict:
    raw = input_fn("section lengths (name=len, comma-sep; blank=default)> ").strip()
    if not raw:
        return {}
    out = {}
    for pair in raw.split(","):
        if "=" in pair:
            k, val = pair.split("=", 1)
            out[k.strip()] = val.strip()
    return out

def _editor_answers(*, input_fn) -> dict:
    out = {}
    while True:
        k = input_fn("editor-answer key (blank to end)> ").strip()
        if not k:
            break
        out[k] = input_fn(f"  {k}) answer> ").strip()
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_agent_gates.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add refereekit/agent/loop.py tests/test_agent_gates.py
git commit -m "feat: agent human gates (verdict, section lengths, editor answers)"
```

---

### Task 4: `run_review` end-to-end + `ReviewResult`

**Files:**
- Modify: `refereekit/agent/loop.py`, `refereekit/agent/__init__.py`
- Test: `tests/test_agent_run_review.py`

**Interfaces:**
- Produces:
  - `@dataclass ReviewResult: report_path, editor_path, flags: list, verdict: dict`.
  - `run_review(pdf_path, *, backend, session_dir, input_fn=input, output_fn=print,
    style_path="style/STYLE.md", memory=None, venue=None) -> ReviewResult` —
    orchestrates: ingest→save_doc; summarize (`complete(summary_prompt+doc,
    manuscript_ok=True)`, `output_fn`); `_qa_loop`; `_verdict_gate`; `_detail_gate`;
    `drafts.report(...)` → write `report.txt`; `_editor_answers`;
    `drafts.editor_letter(...)` → write `editor.txt`; return `ReviewResult` with the
    draft flags + verdict.
  - `refereekit/agent/__init__.py` exports `run_review`, `ReviewResult`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_run_review.py
from refereekit.agent import run_review, ReviewResult
from refereekit.llm import FakeBackend
from refereekit.memory import SQLiteMemoryStore, Note
from refereekit.ingest import ingest

def test_run_review_end_to_end(tmp_path, real_pdf_path):
    mem = SQLiteMemoryStore(tmp_path / "m.db")
    mem.store(Note("PRX: lean accept-after-major", "PRX"), ingest(real_pdf_path),
              created_at="2026-01-01T00:00:00")
    # scripted inputs: one question, sentinel, verdict(3), section-lengths blank,
    # editor answer key + value + blank-to-end
    script = iter([
        "what is the main contribution?", "",          # Q&A
        "major revision", "PRX", "major",              # verdict gate
        "",                                            # detail gate (default)
        "a", "novelty is partial", "",                 # editor answers
    ])
    outputs = []
    res = run_review(real_pdf_path, backend=FakeBackend("Contribution summarized. See p. 1."),
                     session_dir=tmp_path / "s",
                     input_fn=lambda _="": next(script), output_fn=outputs.append,
                     memory=mem, venue="PRX")
    assert isinstance(res, ReviewResult)
    assert res.report_path.exists() and res.editor_path.exists()
    assert res.verdict["venue"] == "PRX"
    assert res.report_path.read_text()  # non-empty draft
    assert any("summar" in o.lower() or "Contribution" in o for o in outputs)  # summary emitted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent_run_review.py -v`
Expected: FAIL — `run_review`/`ReviewResult` not defined.

- [ ] **Step 3: Write minimal implementation**

Add to `refereekit/agent/loop.py` (imports: `from dataclasses import dataclass,
field`; `from pathlib import Path`; `from ..ingest import ingest`; `from ..session
import Session`; `from .. import drafts`):
```python
@dataclass
class ReviewResult:
    report_path: Path
    editor_path: Path
    flags: list = field(default_factory=list)
    verdict: dict = field(default_factory=dict)

def run_review(pdf_path, *, backend, session_dir, input_fn=input, output_fn=print,
               style_path="style/STYLE.md", memory=None, venue=None) -> ReviewResult:
    session_dir = Path(session_dir)
    session = Session.create(session_dir.parent, session_dir.name)
    doc = ingest(pdf_path); session.save_doc(doc)
    # 1. summarize
    from ..llm import complete
    summary = complete(_doc_context(doc, [], "Summarize this paper for a referee."),
                       backend=backend, manuscript_ok=True)
    output_fn("SUMMARY:\n" + summary)
    # 2. Q&A
    _qa_loop(session, doc, backend=backend, input_fn=input_fn, output_fn=output_fn)
    # 3. verdict gate
    verdict = _verdict_gate(session, input_fn=input_fn, output_fn=output_fn)
    # 4. draft
    lengths = _detail_gate(input_fn=input_fn)
    rep = drafts.report(session, verdict, lengths, backend=backend,
                        style_path=style_path, memory=memory, venue=venue)
    report_path = session_dir / "report.txt"; report_path.write_text(rep.text)
    # 5-6. editor
    answers = _editor_answers(input_fn=input_fn)
    ed = drafts.editor_letter(session, answers, backend=backend,
                              style_path=style_path, memory=memory, venue=venue)
    editor_path = session_dir / "editor.txt"; editor_path.write_text(ed.text)
    return ReviewResult(report_path=report_path, editor_path=editor_path,
                        flags=rep.flags + ed.flags, verdict=verdict)
```
Set `refereekit/agent/__init__.py`:
```python
from .loop import run_review, ReviewResult
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_agent_run_review.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add refereekit/agent/loop.py refereekit/agent/__init__.py tests/test_agent_run_review.py
git commit -m "feat: run_review end-to-end orchestrator + ReviewResult"
```

---

### Task 5: CLI `review` command

**Files:**
- Modify: `refereekit/cli.py`
- Test: `tests/test_cli_review.py`

**Interfaces:**
- Produces: `review <pdf> --session S [--venue V] [--db PATH] [--style PATH]`:
  selects `_backend()`; builds an optional `SQLiteMemoryStore` (default
  `<session>/memory.db`) as `memory`; calls `run_review(pdf, backend=..., session_dir=S,
  memory=..., venue=...)` with real stdin/stdout. Setup errors (missing pdf/session)
  or guard/LLM errors → clean stderr + `return 2`. Success → print result summary
  (report/editor paths + flag count) and `return 0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_review.py
import os
from refereekit.cli import main

def test_cli_review_end_to_end_offline(tmp_path, real_pdf_path, monkeypatch, capsys):
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Answer about the paper. See p. 1.")
    script = iter(["a question?", "", "minor revision", "PRX", "minor", "", ""])
    monkeypatch.setattr("builtins.input", lambda _="": next(script))
    rc = main(["review", str(real_pdf_path), "--session", str(tmp_path / "s")])
    assert rc == 0
    assert (tmp_path / "s" / "report.txt").exists()
    assert (tmp_path / "s" / "editor.txt").exists()

def test_cli_review_missing_pdf_exit2(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    rc = main(["review", str(tmp_path / "nope.pdf"), "--session", str(tmp_path / "s")])
    assert rc == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli_review.py -v`
Expected: FAIL — argparse: invalid choice `'review'`.

- [ ] **Step 3: Write minimal implementation**

In `refereekit/cli.py` (imports: `from .agent import run_review`;
`from .memory import SQLiteMemoryStore`; reuse `_backend`, `ManuscriptLeakError`,
`sqlite3`, `Path`, `sys`):
```python
    prv = sub.add_parser("review"); prv.add_argument("pdf"); prv.add_argument("--session", required=True)
    prv.add_argument("--venue"); prv.add_argument("--db"); prv.add_argument("--style", default="style/STYLE.md")
    # dispatch:
    if args.cmd == "review":
        from pathlib import Path as _P
        sdir = _P(args.session)
        db = args.db or str(sdir / "memory.db")
        try:
            mem = SQLiteMemoryStore(db) if args.venue else None
            res = run_review(args.pdf, backend=_backend(), session_dir=sdir,
                             style_path=args.style, memory=mem, venue=args.venue)
        except (FileNotFoundError, ValueError, ManuscriptLeakError, sqlite3.OperationalError) as e:
            print(f"review failed: {e}", file=sys.stderr); return 2
        print(f"review complete: {res.report_path}, {res.editor_path} "
              f"({len(res.flags)} flag(s))"); return 0
```

- [ ] **Step 4: Run test to verify it passes, then full suite**

Run: `.venv/bin/pytest tests/test_cli_review.py -v && .venv/bin/pytest -q`
Expected: target passes; whole suite green.

- [ ] **Step 5: Commit**

```bash
git add refereekit/cli.py tests/test_cli_review.py
git commit -m "feat: CLI review command (standalone end-to-end)"
```

---

### Task 6: Full suite + README + standalone acceptance

**Files:**
- Modify: `README.md`
- Test: whole suite.

- [ ] **Step 1: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: ALL PASS. Report count.

- [ ] **Step 2: Standalone smoke (offline, fixture)**

```bash
REFEREEKIT_FAKE=1 REFEREEKIT_FAKE_TEXT="Answer. See p. 1." \
  printf 'q?\n\nminor\nPRX\nminor\n\n\n' | \
  .venv/bin/refereekit review tests/fixtures/real_paper.pdf --session /tmp/spd --venue PRX
ls /tmp/spd/report.txt /tmp/spd/editor.txt /tmp/spd/index.html
```
Expected: writes report.txt, editor.txt, index.html; exit 0.

- [ ] **Step 3: Update README**

Add a "Standalone review (SP-D)" section: `refereekit review <pdf> --session S
[--venue V]`, the fixed pipeline, that it runs with NO external harness (with a real
zero-retention key: `REFEREEKIT_ZERO_RETENTION=1 REFEREEKIT_MODEL=… refereekit
review …`), and the offline `REFEREEKIT_FAKE=1` mode. Note manuscript text goes only
to the zero-retention LLM; the transcript stays in the session dir.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: SP-D standalone review usage"
```

---

## Self-Review

**Spec coverage:**
- Scripted orchestrator, fixed pipeline (§3) → Tasks 2–4 ✓
- Injectable I/O, testable offline (§3) → all agent tests use `input_fn`/`output_fn` + FakeBackend ✓
- Multi-turn via transcript, `llm` unchanged (§3/§4) → `_doc_context` + `_qa_loop` (Task 1/2); no llm edits ✓
- Q&A anchor re-verification + record into pool (§4/§6) → Task 2 (verified anchors `record_claim`'d so the draft pool is populated; failures flagged) ✓
- init_page before Q&A (§4 1b) → Task 2 ✓
- Verdict + detail gates (§4) → Task 3 ✓
- run_review + ReviewResult (§4) → Task 4 ✓
- CLI review, exit-2 on setup error (§4) → Task 5 ✓
- Suite/README/standalone acceptance (§7) → Task 6 ✓
- Deferred (not built): autonomous agent, Exa-in-loop, multi-turn chat API, quote-match — none added.

**Placeholder scan:** none — complete code + exact commands. (Task 1 Step 3 notes the
`__init__.py`-empty-until-Task-4 sequencing explicitly to avoid an import error.)

**Type consistency:** `_doc_context(doc, transcript, question)`, `_qa_loop(...)->list`,
`_verdict_gate/_detail_gate/_editor_answers`, `run_review(...)->ReviewResult` used
consistently across tasks; reuses verified real signatures (`drafts.report/editor_letter`
with `memory`/`venue`; `render.init_page/append_qa`; `Session.record_claim`;
`verify`/`extract_anchors`). No existing module signature changes.

**Confidentiality:** manuscript text → only `complete()` (unchanged, zero-retention)
and the git-ignored session dir; memory recall read-only; no new egress path; tests
offline with the public fixture.
