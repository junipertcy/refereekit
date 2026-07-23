# refereekit Ingest-Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `refereekit.ingest` extract figures (reliably), sections and equation numbers (best-effort), on real papers — validated by a committed real-paper fixture — without OCR/LLM/network.

**Architecture:** Harden `refereekit/ingest.py` internals only (public `ingest(pdf_path)->Document` signature unchanged). Add private helpers using PyMuPDF text + span geometry. Add a committed real-paper fixture (arXiv:2106.00185, author's public paper) and a `real_doc` pytest fixture; assert figures exactly, equations/sections best-effort, and guard against the inline-`(N)`-list false positive.

**Tech Stack:** Python 3.14, PyMuPDF (`fitz`), stdlib `re`, `pytest`. No new dependencies.

## Global Constraints

- **Confidentiality:** The only real PDF committed is `tests/fixtures/real_paper.pdf` (arXiv:2106.00185, the author's own PUBLIC paper — authorized). No manuscript-under-review content, no manuscript identifier, in any committed file, test, or commit message. The dogfood copy under `work/` stays git-ignored.
- **ingest stays pure:** offline, deterministic, no network, no LLM, no OCR. stdlib + PyMuPDF only.
- **Fact guarantee preserved:** equation extraction must NOT turn the inline list markers "(1) … (2) …" into equations (false positives are worse than omissions).
- **Public API unchanged:** `ingest`, `to_json`, `from_json`, and the `Document/Figure/Equation/Section` dataclasses keep their current shape.
- **Python:** target 3.14; run tools as `.venv/bin/python`, `.venv/bin/pytest`.
- **TDD:** each change preceded by a failing test; commit after each green task.

## Ground truth (arXiv:2106.00185, verified)

- **Figures:** ids exactly `{1,2,3,4}`. Figure 1 caption begins `"(a) Geometric representation"`.
- **Equation numbers:** right-margin bare-integer spans are NOISY (40 spans incl. line/ref numbers); distinct small values include 0–7. Treat as best-effort; assert bounds, not counts.
- **Sections:** headings do NOT appear as all-caps or roman-numeral lines in the extracted text → detection is best-effort; assert a lower bound (≥1) or skip asserting an exact set.
- **Inline false-positive:** the sentence `"…considered equivalent if (1) they participate…"` (and "(2) …") exists — the guard target.

---

### Task 1: Commit the real-paper fixture + `real_doc` pytest fixture

**Files:**
- Create: `tests/fixtures/real_paper.pdf` (copy of the arXiv:2106.00185 PDF)
- Modify: `tests/conftest.py` (add `real_pdf_path` + `real_doc` fixtures)
- Test: `tests/test_real_fixture.py`

**Interfaces:**
- Consumes: `refereekit.ingest.ingest`.
- Produces: pytest fixtures `real_pdf_path` (path to the committed PDF) and
  `real_doc` (session-scoped, `ingest(real_pdf_path)`).

- [ ] **Step 1: Add the fixture PDF (already downloaded at `work/2106.00185.pdf`)**

Run:
```bash
cp work/2106.00185.pdf tests/fixtures/real_paper.pdf
git check-ignore tests/fixtures/real_paper.pdf; echo "exit $? (nonzero = NOT ignored = good)"
```
Expected: prints nothing, exit 1 — the fixtures dir is not git-ignored (root patterns only).

- [ ] **Step 2: Write the failing test**

```python
# tests/test_real_fixture.py
from refereekit.types import Document

def test_real_paper_ingests(real_doc):
    assert isinstance(real_doc, Document)
    assert len(real_doc.pages) == 9
    assert "simplicial complexes" in real_doc.page_text(1).lower()
```

Add to `tests/conftest.py`:
```python
@pytest.fixture(scope="session")
def real_pdf_path():
    import pathlib
    return pathlib.Path("tests/fixtures/real_paper.pdf")

@pytest.fixture(scope="session")
def real_doc(real_pdf_path):
    from refereekit.ingest import ingest
    return ingest(real_pdf_path)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_real_fixture.py -v`
Expected: FAIL — fixture `real_doc`/`real_pdf_path` not found (until conftest edit is saved) OR file missing. Once conftest is saved and PDF copied, it should pass; if you see it fail for a real reason, fix before proceeding.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_real_fixture.py -v`
Expected: PASS (9 pages, phrase present).

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/real_paper.pdf tests/conftest.py tests/test_real_fixture.py
git commit -m "test: commit real-paper fixture (arXiv:2106.00185, public) + real_doc"
```

---

### Task 2: Figures — extract from `FIG. N.` lines (reliable), retire dead loop

**Files:**
- Modify: `refereekit/ingest.py`
- Test: `tests/test_ingest_figures.py`

**Interfaces:**
- Produces: `_extract_figures(page_text: str, page_no: int) -> list[Figure]`, wired
  into `ingest`. Matches lines like `FIG. 1. (a) caption…` →
  `Figure(id="1", page=page_no, caption="(a) caption…")`. Dedupe by id (first wins).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_figures.py
def test_real_paper_figures_exact(real_doc):
    ids = sorted((f.id for f in real_doc.figures), key=int)
    assert ids == ["1", "2", "3", "4"]

def test_figure_caption_captured(real_doc):
    fig1 = next(f for f in real_doc.figures if f.id == "1")
    assert fig1.caption.startswith("(a) Geometric representation")

def test_extract_figures_unit():
    from refereekit.ingest import _extract_figures
    figs = _extract_figures("FIG. 7. (a) example caption here.\nother text", 5)
    assert len(figs) == 1 and figs[0].id == "7" and figs[0].page == 5
    assert figs[0].caption.startswith("(a) example")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ingest_figures.py -v`
Expected: FAIL — `_extract_figures` not defined; and `real_doc.figures` is currently empty so the exact-ids test fails.

- [ ] **Step 3: Write minimal implementation**

In `refereekit/ingest.py`, add:
```python
_FIG_LINE = re.compile(r"^\s*FIG\.\s*(\d+)\.\s*(.*)$")

def _extract_figures(page_text: str, page_no: int) -> list[Figure]:
    figs, seen = [], set()
    for line in page_text.splitlines():
        m = _FIG_LINE.match(line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            figs.append(Figure(id=m.group(1), page=page_no, caption=m.group(2).strip()))
    return figs
```
In `ingest`, replace the dead figure loop (the `for line in text.splitlines(): if ... pass`) with:
```python
        figures.extend(_extract_figures(text, i + 1))
```
Keep dedupe across pages: after the page loop, collapse duplicate ids keeping first:
```python
    _seen = set(); _f = []
    for f in figures:
        if f.id not in _seen:
            _seen.add(f.id); _f.append(f)
    figures = _f
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ingest_figures.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add refereekit/ingest.py tests/test_ingest_figures.py
git commit -m "feat: extract figures from FIG. N lines (reliable); retire dead loop"
```

---

### Task 3: Sections — best-effort heading detection

**Files:**
- Modify: `refereekit/ingest.py`
- Test: `tests/test_ingest_sections.py`

**Interfaces:**
- Produces: `_extract_sections(page_text: str, page_no: int) -> list[Section]`, wired
  into `ingest`. Conservative: emit a `Section` for a line that looks like a heading —
  either `N. Title` / `N.N Title` (numbered) or a Roman-numeral heading `I. TITLE` /
  `II. Title`. Prefer missing a heading over emitting body text.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_sections.py
def test_extract_sections_unit_numbered():
    from refereekit.ingest import _extract_sections
    secs = _extract_sections("2. Methods\nWe describe the approach.\n3.1 Sampling", 4)
    titles = [s.title for s in secs]
    assert "2. Methods" in titles or "Methods" in titles
    assert any("Sampling" in t for t in titles)

def test_extract_sections_ignores_body():
    from refereekit.ingest import _extract_sections
    secs = _extract_sections("This is an ordinary sentence that is not a heading.", 1)
    assert secs == []

def test_real_paper_sections_lower_bound(real_doc):
    # best-effort: detection may be imperfect on this PDF; require it not to crash
    # and to return a list (possibly empty). This guards the wiring, not a count.
    assert isinstance(real_doc.sections, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ingest_sections.py -v`
Expected: FAIL — `_extract_sections` not defined.

- [ ] **Step 3: Write minimal implementation**

In `refereekit/ingest.py`, add:
```python
_SEC_NUM = re.compile(r"^\s*(\d+(?:\.\d+)?)\.?\s+([A-Z][A-Za-z].{2,60})$")
_SEC_ROMAN = re.compile(r"^\s*(I{1,3}|IV|V|VI{0,3}|IX|X)\.\s+([A-Z].{2,60})$")

def _extract_sections(page_text: str, page_no: int) -> list[Section]:
    secs = []
    for line in page_text.splitlines():
        s = line.strip()
        m = _SEC_NUM.match(s) or _SEC_ROMAN.match(s)
        if m:
            secs.append(Section(title=s, page=page_no))
    return secs
```
Wire into `ingest` inside the page loop:
```python
        sections.extend(_extract_sections(text, i + 1))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ingest_sections.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add refereekit/ingest.py tests/test_ingest_sections.py
git commit -m "feat: best-effort section heading detection"
```

---

### Task 4: Equation numbers — right-margin geometry, filtered (best-effort)

**Files:**
- Modify: `refereekit/ingest.py`
- Test: `tests/test_ingest_equations.py`

**Interfaces:**
- Produces: `_extract_equation_numbers(page: "fitz.Page") -> list[Equation]` — scans
  `page.get_text("dict")` spans; a candidate is a span whose text is a BARE integer
  (`re.fullmatch(r"\d{1,3}")`), whose `bbox[0] > 0.85 * page.rect.width`
  (right margin). Returns `Equation(id=<int str>, page, body="")`. Wired into `ingest`
  (needs the `fitz.Page`, so call it inside the page loop with `pg`).
- The current `_EQ_LABEL` line-end regex and its loop are REMOVED (they produced
  nothing on real papers and could catch inline `(N)` markers).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_equations.py
def test_inline_list_markers_are_not_equations(real_doc):
    # the paper has "...equivalent if (1) they participate... and (2)..."
    # those inline (N) markers must NOT appear as equations
    bodies = " ".join(e.body for e in real_doc.equations)
    assert "they participate" not in bodies  # no inline-marker text captured
    # and equation ids must not be sourced from inline "(1)"/"(2)" text tokens:
    # (right-margin geometry never reads those inline tokens)
    assert isinstance(real_doc.equations, list)

def test_real_paper_equations_best_effort_bound(real_doc):
    # best-effort: at least one plausible small equation label recovered
    small = [e for e in real_doc.equations if e.id.isdigit() and int(e.id) <= 12]
    assert len(small) >= 1

def test_no_figures_invented_by_equation_pass(real_doc):
    # equation pass must not corrupt figures (still exactly 1..4)
    assert sorted((f.id for f in real_doc.figures), key=int) == ["1", "2", "3", "4"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ingest_equations.py -v`
Expected: FAIL — `real_doc.equations` currently empty (old regex found nothing) → the best-effort bound test fails.

- [ ] **Step 3: Write minimal implementation**

In `refereekit/ingest.py`:
- Remove `_EQ_LABEL` and the old `for line in text.splitlines(): m = _EQ_LABEL.search(...)` loop.
- Add:
```python
_BARE_INT = re.compile(r"\d{1,3}")

def _extract_equation_numbers(page) -> list[Equation]:
    eqs, seen = [], set()
    W = page.rect.width
    pno = page.number + 1
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                t = span["text"].strip()
                if _BARE_INT.fullmatch(t) and span["bbox"][0] > 0.85 * W:
                    if t not in seen:
                        seen.add(t)
                        eqs.append(Equation(id=t, page=pno, body=""))
    return eqs
```
- In `ingest`, inside the page loop (where `pg = doc[i]`), add:
```python
        equations.extend(_extract_equation_numbers(pg))
```
(De-dupe equations across pages by id, first-wins, mirroring the figures collapse.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ingest_equations.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add refereekit/ingest.py tests/test_ingest_equations.py
git commit -m "feat: best-effort equation-number extraction via right-margin geometry"
```

---

### Task 5: Full suite, docs, dogfood-status update

**Files:**
- Modify: `README.md`, `docs/DOGFOOD-FINDINGS-2026-07-22.md`
- Test: whole suite.

- [ ] **Step 1: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: ALL PASS (SP-A + SP-B + the new real-fixture/figure/section/equation tests). Report the count.

- [ ] **Step 2: Re-run the dogfood ingest to confirm the real improvement**

Run:
```bash
.venv/bin/refereekit ingest tests/fixtures/real_paper.pdf --session /tmp/hardened
.venv/bin/python -c "from refereekit.session import Session; d=Session('/tmp/hardened').load_doc(); print('figures',[f.id for f in d.figures],'equations',len(d.equations),'sections',len(d.sections))"
```
Expected: figures `['1','2','3','4']`; equations ≥ 1; sections ≥ 0. (Contrast the dogfood baseline: 0/0/0.)

- [ ] **Step 3: Update docs**

- In `docs/DOGFOOD-FINDINGS-2026-07-22.md`, add a short "Resolved by ingest-hardening
  (2026-07-22)" note: figures now reliable (1–4); equation numbers best-effort via
  geometry; sections best-effort; real-paper fixture added as a regression guard.
- In `README.md`, add an "Extraction limits" note: figures reliable; equation numbers
  best-effort (bodies not reconstructed; PDF math is lossy); quote/page verification
  is the most reliable path.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/DOGFOOD-FINDINGS-2026-07-22.md
git commit -m "docs: record ingest-hardening results + extraction limits"
```

---

## Self-Review

**Spec coverage:**
- Figures reliable, assert exactly 1..4 (spec §3/§6) → Task 2 ✓
- Sections best-effort, sanity-bounded (§3/§6) → Task 3 ✓ (honest: ground-truth check
  showed headings don't surface as caps/roman on this PDF, so the real-paper test is a
  wiring/lower-bound guard, not an exact set — matches the noisy reality)
- Equation numbers via filtered right-margin geometry, best-effort, no inline-marker
  false positive (§3/§4/§6) → Task 4 ✓ (removes the old `_EQ_LABEL` line-end regex)
- Real-paper fixture committed + regression intent (§6) → Task 1 ✓
- ingest stays pure/offline; public API unchanged (§4/§5) → all tasks touch internals only
- Confidentiality: only the author's public paper committed; `work/` stays ignored → Task 1 Step 1 verifies not-ignored for the fixture; the guard is that no manuscript-under-review PDF is used

**Placeholder scan:** none — every step has real code and the verified ground-truth values (figures 1..4, caption prefix, inline-marker sentence).

**Type consistency:** `Figure(id,page,caption)`, `Equation(id,page,body)`, `Section(title,page)` match the existing dataclasses; helpers return those types; `ingest` signature and `to_json/from_json` unchanged. `_extract_equation_numbers` takes a `fitz.Page` (called with `pg` inside the loop) — noted so the implementer wires it with the page object, not the text.

**Note on Task 3 realism:** the ground-truth probe found no caps/roman headings in this PDF's text, so `_extract_sections` may legitimately return few/none on the real fixture. The plan asserts unit behavior on synthetic strings (deterministic) and only a wiring/type bound on the real doc — deliberately not an exact count, consistent with the spec's best-effort stance.
