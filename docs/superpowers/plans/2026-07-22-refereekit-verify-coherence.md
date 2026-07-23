# refereekit Verify-Coherence Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix two coherence issues found by the second dogfood pass (see
`docs/DOGFOOD-FINDINGS-2-2026-07-22.md`): (1) `verify --kind figure` ignores the
now-populated `doc.figures` and always FLAGs; (2) an ingest noise id `"0"` makes
`verify equation 0` spuriously PASS.

**Architecture:** Two small, independent internal fixes — `refereekit/verify.py`
(figure existence branch) and `refereekit/ingest.py` (drop equation id "0"). No API
changes, no new deps, offline/deterministic. Real-paper fixture + synthetic tests.

**Tech Stack:** Python 3.14, PyMuPDF, stdlib, pytest.

## Global Constraints

- Confidentiality: no manuscript-under-review text/identifier committed; only the
  existing public fixtures are used.
- ingest/verify stay pure, offline, deterministic; stdlib + PyMuPDF only.
- Public API unchanged: `verify(Claim, Document)->Verdict`, `ingest(pdf)->Document`,
  dataclasses, `to_json/from_json`.
- Fact guarantee preserved/strengthened: figure existence is checked (not blindly
  FLAGged); noise id "0" no longer PASSes.
- TDD: failing test first; commit per task.
- Ground truth (verified): real fixture has figures {1,2,3,4}; equation ids include
  real labels 1..7 plus noise incl. "0".

---

### Task 1: Figure verify — existence PASS/FAIL (mirror equations)

**Files:**
- Modify: `refereekit/verify.py`
- Test: `tests/test_verify_figures.py`

**Interfaces:**
- Consumes: `Claim`, `Document.figures` (each `Figure` has `.id`).
- Produces: in `verify`, a `kind == "figure"` branch: PASS if any figure with
  `id == claim.anchor` exists, else FAIL. (Content claims are not separately modeled;
  the referee cites a figure number and we confirm it exists.) The catch-all FLAG
  remains for genuinely unknown kinds.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_verify_figures.py
from refereekit.verify import verify
from refereekit.types import Claim

def test_existing_figure_passes(real_doc):
    v = verify(Claim("", "figure", "1"), real_doc)
    assert v.status == "PASS"

def test_absent_figure_fails(real_doc):
    v = verify(Claim("", "figure", "9"), real_doc)
    assert v.status == "FAIL"

def test_unknown_kind_still_flags(real_doc):
    v = verify(Claim("", "table", "1"), real_doc)
    assert v.status == "FLAG"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_verify_figures.py -v`
Expected: FAIL — `test_existing_figure_passes` and `test_absent_figure_fails` get
FLAG (current catch-all) instead of PASS/FAIL.

- [ ] **Step 3: Write minimal implementation**

In `refereekit/verify.py`, add a figure branch BEFORE the final catch-all (mirror the
equation branch at lines 20-23):
```python
    if claim.kind == "figure":
        if any(f.id == claim.anchor for f in doc.figures):
            return Verdict("PASS", f"figure ({claim.anchor}) exists")
        return Verdict("FAIL", f"figure ({claim.anchor}) not found")
```
Leave the final `return Verdict("FLAG", ...)` for unknown kinds intact.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_verify_figures.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add refereekit/verify.py tests/test_verify_figures.py
git commit -m "fix: verify figure kind checks existence (PASS/FAIL), not blanket FLAG"
```

---

### Task 2: Ingest — drop equation id "0" (noise)

**Files:**
- Modify: `refereekit/ingest.py`
- Test: `tests/test_ingest_equations.py` (add a case)

**Interfaces:**
- Modify `_extract_equation_numbers`: skip a span whose integer text is `"0"`
  (never a real equation label). Keep all ids `>= 1`. Everything else unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ingest_equations.py`:
```python
def test_equation_id_zero_is_filtered(real_doc):
    ids = {e.id for e in real_doc.equations}
    assert "0" not in ids  # "0" is never a real equation label

def test_zero_excluded_unit():
    import fitz
    from refereekit.ingest import _extract_equation_numbers
    doc = fitz.open(); page = doc.new_page(width=612, height=792)
    page.insert_text((560, 150), "0")   # right margin, but not a real label
    page.insert_text((560, 250), "5")   # right margin, real label
    ids = {e.id for e in _extract_equation_numbers(page)}
    assert ids == {"5"}
    doc.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ingest_equations.py -v`
Expected: FAIL — real_doc currently includes "0"; unit test finds `{"0","5"}`.

- [ ] **Step 3: Write minimal implementation**

In `_extract_equation_numbers`, when building the candidate, skip `"0"`:
```python
                if _BARE_INT.fullmatch(t) and span["bbox"][0] > 0.85 * W:
                    if t == "0":
                        continue
                    if t not in seen:
                        seen.add(t)
                        eqs.append(Equation(id=t, page=pno, body=""))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ingest_equations.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add refereekit/ingest.py tests/test_ingest_equations.py
git commit -m "fix: drop equation id '0' (noise) at ingest"
```

---

### Task 3: Full suite + docs

**Files:**
- Modify: `docs/DOGFOOD-FINDINGS-2-2026-07-22.md`
- Test: whole suite.

- [ ] **Step 1: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: ALL PASS. Report the count.

- [ ] **Step 2: Re-verify the fixes on the real paper**

```bash
.venv/bin/refereekit ingest tests/fixtures/real_paper.pdf --session /tmp/vc
.venv/bin/refereekit verify --session /tmp/vc --kind figure --anchor 1 --text x   # PASS, exit 0
.venv/bin/refereekit verify --session /tmp/vc --kind figure --anchor 9 --text x   # FAIL, exit 1
.venv/bin/refereekit verify --session /tmp/vc --kind equation --anchor 0 --text x # FAIL now (was PASS)
```
Expected: figure 1 PASS(0), figure 9 FAIL(1), equation 0 FAIL(1).

- [ ] **Step 3: Update the dogfood-2 doc**

Mark Findings 1 and 2 resolved: figure verify now existence-based (PASS/FAIL);
equation id "0" filtered at ingest (noise ids >=1 like 22/30 remain, documented
best-effort). Note residual: verbatim quote matching still open.

- [ ] **Step 4: Commit**

```bash
git add docs/DOGFOOD-FINDINGS-2-2026-07-22.md
git commit -m "docs: mark dogfood-2 findings resolved (figure verify, noise id)"
```

---

## Self-Review

- **Coverage:** Finding 1 → Task 1 (figure existence, unknown-kind still FLAG) ✓;
  Finding 2 → Task 2 (drop "0", unit + real-doc assertions) ✓; suite/docs → Task 3 ✓.
- **Placeholders:** none; complete code + exact commands.
- **Type consistency:** `verify(Claim, Document)->Verdict` unchanged; figure branch
  mirrors equation branch exactly (`.id == claim.anchor`); `_extract_equation_numbers`
  keeps its signature and only adds a `"0"` skip.
- **Fact guarantee:** strengthened — figure existence now checked; noise "0" no longer
  PASSes. Real labels 1..7 and figures 1..4 unaffected.
- **Deferred (not this cycle):** quote-match normalization; contiguous-run equation
  filtering (chose conservative drop-"0" only); report/editor DRY; diagram refresh.
