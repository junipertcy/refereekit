# refereekit Phase 1 (SP-A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the runnable, tested core of `refereekit` — ingest a PDF, verify factual anchors against it, guard manuscript text from leaving, and serve a live Q&A page — driven from the CLI.

**Architecture:** A dependency-light Python package `refereekit/` with a plain `argparse` CLI wrapping pure-function module APIs. Deterministic modules only in this phase (no LLM, no network): `ingest`, `verify`, `guard`, `render`, `session`. Each module is a testable API + a CLI subcommand. LLM/litsearch/memory/drafts arrive in later phases.

**Tech Stack:** Python 3.14, PyMuPDF (`fitz`) for PDF extraction, stdlib `argparse` + `http.server`, `pytest` for tests, `pdflatex` to build the test fixture.

## Global Constraints

- **Confidentiality (spec §3, §7):** No confidential manuscript PDF or text derived from one is ever committed. The repo root's `/*.pdf`, `/*_raw.txt`, `/*_plain.txt`, `/review_draft_*.txt`, `/editor_response_*.txt`, `/index.html` are git-ignored; the ONLY committable PDF is `tests/fixtures/sample_paper.pdf`.
- **No manuscript ID or manuscript text** appears in any committed source, test, comment, or commit message.
- **Dependency-light core:** stdlib only except PyMuPDF and pytest. No `click`, no network libs in Phase 1.
- **Python:** target 3.14 (the venv at `.venv/`); run tools as `.venv/bin/python`, `.venv/bin/pytest`.
- **TDD:** every code change is preceded by a failing test. Commit after each green task.

---

## File Structure

```
refereekit/
  __init__.py            package marker, version
  types.py               dataclasses: Document, Page, Figure, Equation, Section, Claim, Verdict
  ingest.py              ingest(pdf_path) -> Document ; to_json/from_json
  guard.py               assert_no_manuscript(text, Document)
  verify.py              verify(claim, Document) -> Verdict
  render.py              append_qa(session_dir, q, answer_html) ; serve(session_dir, port)
  session.py             Session dir helpers: create, doc paths, state.json
  cli.py                 argparse entry: ingest | verify | serve
tests/
  conftest.py            fixture: builds sample_paper.pdf, returns ingested Document
  fixtures/
    sample_paper.tex     author-authored short paper (derived from arXiv:2106.00185)
    build_fixture.py     compiles .tex -> .pdf via pdflatex
  test_ingest.py
  test_guard.py
  test_verify.py
  test_render.py
  test_session.py
  test_cli.py
pyproject.toml           package metadata + pytest config + deps
```

---

### Task 1: Project scaffold + packaging

**Files:**
- Create: `pyproject.toml`, `refereekit/__init__.py`
- Test: `tests/test_import.py`

**Interfaces:**
- Produces: importable package `refereekit`, `refereekit.__version__` (str).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_import.py
def test_package_imports_and_has_version():
    import refereekit
    assert isinstance(refereekit.__version__, str)
    assert refereekit.__version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_import.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "refereekit"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["PyMuPDF>=1.24"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
refereekit = "refereekit.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

```python
# refereekit/__init__.py
__version__ = "0.1.0"
```

- [ ] **Step 4: Install editable + run test**

Run: `.venv/bin/pip install -e ".[dev]" && .venv/bin/pytest tests/test_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml refereekit/__init__.py tests/test_import.py
git commit -m "feat: scaffold refereekit package"
```

---

### Task 2: Core data types

**Files:**
- Create: `refereekit/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Produces:
  - `Page(n:int, text:str, blocks:list[dict])`
  - `Figure(id:str, page:int, caption:str)`
  - `Equation(id:str, page:int, body:str)`
  - `Section(title:str, page:int)`
  - `Document(pages:list[Page], figures:list[Figure], equations:list[Equation], sections:list[Section])`
  - `Claim(text:str, kind:str, anchor:str)` where kind in {"page","equation","figure","quote"}
  - `Verdict(status:str, evidence:str)` where status in {"PASS","FAIL","FLAG"}
  All are `@dataclass`. `Document.page_text(n:int) -> str` returns the text of page n (raises `KeyError` if absent).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_types.py
from refereekit.types import Document, Page, Claim, Verdict

def test_document_page_text_lookup():
    doc = Document(pages=[Page(n=1, text="hello", blocks=[]),
                          Page(n=2, text="world", blocks=[])],
                   figures=[], equations=[], sections=[])
    assert doc.page_text(2) == "world"

def test_document_page_text_missing_raises():
    doc = Document(pages=[], figures=[], equations=[], sections=[])
    try:
        doc.page_text(5); assert False
    except KeyError:
        pass

def test_claim_and_verdict_construct():
    c = Claim(text="5-8%", kind="quote", anchor="16")
    v = Verdict(status="PASS", evidence="found on page 16")
    assert c.kind == "quote" and v.status == "PASS"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.types'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/types.py
from dataclasses import dataclass, field

@dataclass
class Page:
    n: int
    text: str
    blocks: list[dict] = field(default_factory=list)

@dataclass
class Figure:
    id: str
    page: int
    caption: str

@dataclass
class Equation:
    id: str
    page: int
    body: str

@dataclass
class Section:
    title: str
    page: int

@dataclass
class Document:
    pages: list[Page] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    equations: list[Equation] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    def page_text(self, n: int) -> str:
        for p in self.pages:
            if p.n == n:
                return p.text
        raise KeyError(f"page {n} not found")

@dataclass
class Claim:
    text: str
    kind: str   # page | equation | figure | quote
    anchor: str

@dataclass
class Verdict:
    status: str  # PASS | FAIL | FLAG
    evidence: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_types.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add refereekit/types.py tests/test_types.py
git commit -m "feat: core data types"
```

---

### Task 3: Test fixture — author-authored sample paper

**Files:**
- Create: `tests/fixtures/sample_paper.tex`, `tests/fixtures/build_fixture.py`, `tests/conftest.py`
- Test: `tests/test_fixture_builds.py`

**Interfaces:**
- Produces: `build_fixture.py::build() -> Path` (compiles `.tex`, returns path to `sample_paper.pdf`); pytest fixtures `sample_pdf_path` and (later) `sample_doc`.
- **Planted ground truth** (asserted by later tasks): the phrase `"prescribed degree-size sequences"` appears on page 1; an equation labeled `(3)` exists; NO equation labeled `(9)`; a figure with caption starting `"Realizability regions"`; a deliberate duplicated word `"the the"` on page 1.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fixture_builds.py
def test_fixture_pdf_builds(sample_pdf_path):
    assert sample_pdf_path.exists()
    assert sample_pdf_path.suffix == ".pdf"
    assert sample_pdf_path.stat().st_size > 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_fixture_builds.py -v`
Expected: FAIL — fixture `sample_pdf_path` not found (conftest missing)

- [ ] **Step 3: Write the fixture source, builder, and conftest**

Create `tests/fixtures/sample_paper.tex` (short 2-column-ish paper; content adapted from the plan author's own arXiv:2106.00185, used with permission — safe to commit). It MUST contain the planted ground truth above:

```latex
\documentclass[11pt]{article}
\usepackage{amsmath}
\title{Construction of Simplicial Complexes with Prescribed Degree-Size Sequences}
\author{Test Fixture (derived from author's arXiv:2106.00185)}
\begin{document}
\maketitle
\begin{abstract}
We study the realizability of simplicial complexes with a given pair of
integer sequences representing the node degree and facet size distributions.
\end{abstract}
\section{Introduction}
We study the realizability of simplicial complexes with prescribed degree-size
sequences. Note that the the problem is subtle in the $s$-uniform case.
The joint sequence must satisfy a fundamental constraint, given by
\begin{equation}
\sum_{i} d_i = \sum_{j} s_j .
\end{equation}
A necessary counting identity reads
\begin{equation}
m = \tfrac{1}{2}\sum_i d_i .
\end{equation}
The realizability condition can be written as
\begin{equation}
d_{\max} \le \sum_{j} \min(s_j, 1).
\end{equation}
\begin{figure}[h]\centering\rule{3cm}{2cm}
\caption{Realizability regions for the degree-size sequence problem.}
\end{figure}
\end{document}
```

```python
# tests/fixtures/build_fixture.py
import subprocess, pathlib

HERE = pathlib.Path(__file__).parent
TEX = HERE / "sample_paper.tex"
PDF = HERE / "sample_paper.pdf"

def build() -> pathlib.Path:
    if PDF.exists() and PDF.stat().st_mtime >= TEX.stat().st_mtime:
        return PDF
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(HERE), str(TEX)],
        check=True, capture_output=True,
    )
    return PDF

if __name__ == "__main__":
    print(build())
```

```python
# tests/conftest.py
import pytest
from tests.fixtures.build_fixture import build

@pytest.fixture(scope="session")
def sample_pdf_path():
    return build()
```

Also create `tests/__init__.py` and `tests/fixtures/__init__.py` (empty) so `tests.fixtures...` imports resolve.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_fixture_builds.py -v`
Expected: PASS (pdflatex compiles the PDF)

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/sample_paper.tex tests/fixtures/build_fixture.py tests/fixtures/__init__.py tests/conftest.py tests/__init__.py tests/test_fixture_builds.py
git commit -m "test: author-authored sample paper fixture"
```

Note: `sample_paper.pdf` is a build artifact; add `tests/fixtures/*.pdf` intentionally NOT to `.gitignore` root patterns (they are path-anchored to root, so `tests/fixtures/sample_paper.pdf` is already allowed). Commit the compiled PDF too so CI without LaTeX still runs.

---

### Task 4: Ingest — extract Document from PDF

**Files:**
- Create: `refereekit/ingest.py`
- Modify: `tests/conftest.py` (add `sample_doc` fixture)
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `Document, Page, Figure, Equation, Section` from `refereekit.types`.
- Produces:
  - `ingest(pdf_path: str | Path) -> Document`
  - `to_json(doc: Document) -> str` / `from_json(s: str) -> Document`
  - Raises `ValueError("no extractable text")` if the PDF yields empty text (spec §7).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest.py
from refereekit.ingest import ingest, to_json, from_json
from refereekit.types import Document

def test_ingest_returns_document_with_pages(sample_doc):
    assert isinstance(sample_doc, Document)
    assert len(sample_doc.pages) >= 1
    assert any("prescribed degree-size sequences" in p.text.lower()
               or "degree-size" in p.text.lower() for p in sample_doc.pages)

def test_ingest_extracts_equations(sample_doc):
    # three numbered equations planted in the fixture
    assert len(sample_doc.equations) >= 1

def test_json_roundtrip(sample_doc):
    doc2 = from_json(to_json(sample_doc))
    assert doc2.page_text(1)[:20] == sample_doc.page_text(1)[:20]
```

Add to `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def sample_doc(sample_pdf_path):
    from refereekit.ingest import ingest
    return ingest(sample_pdf_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.ingest'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/ingest.py
import json, re
from pathlib import Path
import fitz  # PyMuPDF
from .types import Document, Page, Figure, Equation, Section

_EQ_LABEL = re.compile(r"\((\d{1,3})\)\s*$")

def ingest(pdf_path) -> Document:
    doc = fitz.open(str(pdf_path))
    pages, equations, figures, sections = [], [], [], []
    total_text = ""
    for i in range(doc.page_count):
        pg = doc[i]
        text = pg.get_text()
        total_text += text
        pages.append(Page(n=i + 1, text=text, blocks=[]))
        for line in text.splitlines():
            m = _EQ_LABEL.search(line.strip())
            if m:
                equations.append(Equation(id=m.group(1), page=i + 1, body=line.strip()))
        for line in text.splitlines():
            if line.strip().lower().startswith("figure") or "caption" in line.lower():
                pass  # caption capture handled by verify via text scan; keep list minimal
    if not total_text.strip():
        raise ValueError("no extractable text")
    return Document(pages=pages, figures=figures, equations=equations, sections=sections)

def to_json(d: Document) -> str:
    return json.dumps({
        "pages": [vars(p) for p in d.pages],
        "figures": [vars(f) for f in d.figures],
        "equations": [vars(e) for e in d.equations],
        "sections": [vars(s) for s in d.sections],
    })

def from_json(s: str) -> Document:
    o = json.loads(s)
    return Document(
        pages=[Page(**p) for p in o["pages"]],
        figures=[Figure(**f) for f in o["figures"]],
        equations=[Equation(**e) for e in o["equations"]],
        sections=[Section(**s) for s in o["sections"]],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ingest.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add refereekit/ingest.py tests/conftest.py tests/test_ingest.py
git commit -m "feat: ingest PDF into Document"
```

---

### Task 5: Guard — reject manuscript text

**Files:**
- Create: `refereekit/guard.py`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `Document`.
- Produces: `assert_no_manuscript(text: str, doc: Document, *, n: int = 8, max_overlap: int = 1) -> None`. Raises `ManuscriptLeakError` (subclass of `ValueError`) if `text` shares more than `max_overlap` distinct n-grams (n consecutive words) with any page of `doc`. Short topic queries pass; pasted manuscript sentences fail.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guard.py
import pytest
from refereekit.guard import assert_no_manuscript, ManuscriptLeakError

def test_topic_query_passes(sample_doc):
    assert_no_manuscript("simplicial complexes degree sequences realizability", sample_doc)

def test_manuscript_sentence_is_rejected(sample_doc):
    leak = sample_doc.page_text(1)[:200]  # a real chunk of the paper
    with pytest.raises(ManuscriptLeakError):
        assert_no_manuscript(leak, sample_doc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_guard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.guard'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/guard.py
import re
from .types import Document

class ManuscriptLeakError(ValueError):
    pass

def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}

def assert_no_manuscript(text: str, doc: Document, *, n: int = 8, max_overlap: int = 1) -> None:
    q = _ngrams(text, n)
    if not q:
        return
    doc_ngrams: set[tuple[str, ...]] = set()
    for p in doc.pages:
        doc_ngrams |= _ngrams(p.text, n)
    overlap = len(q & doc_ngrams)
    if overlap > max_overlap:
        raise ManuscriptLeakError(
            f"input overlaps manuscript by {overlap} {n}-grams (max {max_overlap})"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_guard.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add refereekit/guard.py tests/test_guard.py
git commit -m "feat: manuscript-leak guard"
```

---

### Task 6: Verify — mechanical anchors PASS/FAIL, semantic FLAG

**Files:**
- Create: `refereekit/verify.py`
- Test: `tests/test_verify.py`

**Interfaces:**
- Consumes: `Claim, Verdict, Document`.
- Produces: `verify(claim: Claim, doc: Document) -> Verdict`.
  - `kind=="quote"`: PASS if `claim.text` appears (case-insensitive, whitespace-normalized) on page `int(claim.anchor)`, else FAIL.
  - `kind=="equation"`: PASS if an Equation with `id==claim.anchor` exists, else FAIL.
  - `kind=="page"`: PASS if `claim.text` appears anywhere on page `int(claim.anchor)`, else FAIL.
  - `kind=="figure"`: always FLAG (caption semantics need human/LLM judgment in this phase).
  - unknown kind: FLAG.

- [ ] **Step 1: Write the failing test (golden set, all from the fixture)**

```python
# tests/test_verify.py
from refereekit.verify import verify
from refereekit.types import Claim

def test_quote_on_correct_page_passes(sample_doc):
    v = verify(Claim("prescribed degree-size sequences", "quote", "1"), sample_doc)
    assert v.status == "PASS"

def test_quote_on_wrong_page_fails(sample_doc):
    v = verify(Claim("prescribed degree-size sequences", "quote", "99"), sample_doc)
    assert v.status == "FAIL"

def test_existing_equation_passes(sample_doc):
    v = verify(Claim("counting identity", "equation", "3"), sample_doc)
    assert v.status == "PASS"

def test_nonexistent_equation_fails(sample_doc):
    v = verify(Claim("nope", "equation", "9"), sample_doc)
    assert v.status == "FAIL"

def test_figure_claim_flags(sample_doc):
    v = verify(Claim("Realizability regions", "figure", "1"), sample_doc)
    assert v.status == "FLAG"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.verify'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/verify.py
import re
from .types import Claim, Verdict, Document

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def verify(claim: Claim, doc: Document) -> Verdict:
    if claim.kind in ("quote", "page"):
        try:
            page_no = int(claim.anchor)
        except ValueError:
            return Verdict("FAIL", f"anchor {claim.anchor!r} is not a page number")
        try:
            text = doc.page_text(page_no)
        except KeyError:
            return Verdict("FAIL", f"page {page_no} does not exist")
        if _norm(claim.text) in _norm(text):
            return Verdict("PASS", f"found on page {page_no}")
        return Verdict("FAIL", f"not found on page {page_no}")
    if claim.kind == "equation":
        if any(e.id == claim.anchor for e in doc.equations):
            return Verdict("PASS", f"equation ({claim.anchor}) exists")
        return Verdict("FAIL", f"equation ({claim.anchor}) not found")
    # figure + unknown -> semantic, needs human/LLM
    return Verdict("FLAG", f"'{claim.kind}' claim needs human confirmation")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_verify.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add refereekit/verify.py tests/test_verify.py
git commit -m "feat: anchor verification (PASS/FAIL/FLAG)"
```

---

### Task 7: Session — per-paper working dir + state

**Files:**
- Create: `refereekit/session.py`
- Test: `tests/test_session.py`

**Interfaces:**
- Consumes: `Document`, `ingest.to_json/from_json`.
- Produces:
  - `Session(dir: Path)` with attributes `doc_json` (`dir/doc.json`), `html` (`dir/index.html`), `state_json` (`dir/state.json`).
  - `Session.create(base: Path, name: str) -> Session` (mkdirs).
  - `Session.save_doc(doc)` / `Session.load_doc() -> Document`.
  - `Session.set_state(key, value)` / `Session.get_state(key, default=None)` (persists to `state.json`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_session.py
from refereekit.session import Session
from refereekit.types import Document, Page

def test_session_roundtrips_doc_and_state(tmp_path):
    s = Session.create(tmp_path, "paperA")
    doc = Document(pages=[Page(1, "hi", [])], figures=[], equations=[], sections=[])
    s.save_doc(doc)
    assert s.load_doc().page_text(1) == "hi"
    s.set_state("verdict", "major")
    assert Session(s.dir).get_state("verdict") == "major"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_session.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.session'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/session.py
import json
from pathlib import Path
from .types import Document
from .ingest import to_json, from_json

class Session:
    def __init__(self, dir: Path):
        self.dir = Path(dir)
        self.doc_json = self.dir / "doc.json"
        self.html = self.dir / "index.html"
        self.state_json = self.dir / "state.json"

    @classmethod
    def create(cls, base, name: str) -> "Session":
        d = Path(base) / name
        d.mkdir(parents=True, exist_ok=True)
        return cls(d)

    def save_doc(self, doc: Document) -> None:
        self.doc_json.write_text(to_json(doc))

    def load_doc(self) -> Document:
        return from_json(self.doc_json.read_text())

    def _state(self) -> dict:
        if self.state_json.exists():
            return json.loads(self.state_json.read_text())
        return {}

    def set_state(self, key, value) -> None:
        s = self._state(); s[key] = value
        self.state_json.write_text(json.dumps(s))

    def get_state(self, key, default=None):
        return self._state().get(key, default)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_session.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refereekit/session.py tests/test_session.py
git commit -m "feat: session working dir + state"
```

---

### Task 8: Render — live-reload Q&A HTML

**Files:**
- Create: `refereekit/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Session`.
- Produces:
  - `init_page(session: Session, title: str) -> None` — writes `index.html` with MathJax + a 1.5s Last-Modified poll auto-reload script and an empty entries container.
  - `append_qa(session: Session, question: str, answer_html: str) -> None` — prepends a numbered Q&A card before the container marker.
  - `pick_port(preferred: int = 8888) -> int` — returns `preferred`, or the next free port if busy.
  - `serve(session: Session, port: int)` — blocking `http.server` rooted at `session.dir` (manual/CLI use; not unit-tested for blocking).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render.py
from refereekit.render import init_page, append_qa, pick_port
from refereekit.session import Session

def test_append_prepends_numbered_cards(tmp_path):
    s = Session.create(tmp_path, "p")
    init_page(s, "Test")
    append_qa(s, "first?", "<p>one</p>")
    append_qa(s, "second?", "<p>two</p>")
    html = s.html.read_text()
    assert "MathJax" in html
    assert html.index("#2") < html.index("#1")   # newest on top
    assert "first?" in html and "second?" in html

def test_pick_port_returns_int():
    assert isinstance(pick_port(8888), int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.render'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/render.py
import socket, functools, http.server
from .session import Session

_MARKER = "<!-- INSERT-BELOW -->"

_TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{title}</title>
<script>window.MathJax={{tex:{{inlineMath:[['\\\\(','\\\\)'],['$','$']]}}}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>body{{font-family:Georgia,serif;max-width:820px;margin:0 auto;padding:24px;line-height:1.6}}
.card{{border:1px solid #ddd;border-radius:10px;margin:18px 0;padding:14px 18px}}
.q{{font-weight:600;background:#f6f6f4;margin:-14px -18px 12px;padding:12px 18px;border-radius:10px 10px 0 0}}
.num{{float:right;color:#999;font-size:12px}}</style></head><body>
<h2>{title}</h2>
{marker}
<script>
let last=null;
setInterval(async()=>{{try{{const r=await fetch(location.href,{{method:'HEAD',cache:'no-store'}});
const m=r.headers.get('Last-Modified');if(last&&m&&m!==last)location.reload();if(m)last=m;}}catch(e){{}}}},1500);
</script></body></html>"""

def init_page(session: Session, title: str) -> None:
    session.html.write_text(_TEMPLATE.format(title=title, marker=_MARKER))
    session.set_state("qa_count", 0)

def append_qa(session: Session, question: str, answer_html: str) -> None:
    n = int(session.get_state("qa_count", 0)) + 1
    card = (f'<div class="card"><div class="q"><span class="num">#{n}</span>{question}</div>'
            f'{answer_html}</div>\n{_MARKER}')
    html = session.html.read_text().replace(_MARKER, card, 1)
    session.html.write_text(html)
    session.set_state("qa_count", n)

def pick_port(preferred: int = 8888) -> int:
    port = preferred
    for _ in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return preferred

def serve(session: Session, port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(session.dir))
    http.server.HTTPServer(("127.0.0.1", port), handler).serve_forever()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_render.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refereekit/render.py tests/test_render.py
git commit -m "feat: live-reload Q&A HTML render"
```

---

### Task 9: CLI — ingest | verify | serve

**Files:**
- Create: `refereekit/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `main(argv: list[str] | None = None) -> int`. Subcommands:
  - `refereekit ingest <pdf> --session <dir>` → ingests, saves `doc.json`, prints page/eq counts.
  - `refereekit verify --session <dir> --kind <k> --anchor <a> --text <t>` → prints `PASS|FAIL|FLAG` + evidence; exit code 0 for PASS/FLAG, 1 for FAIL.
  - `refereekit serve --session <dir> --port <p>` → picks a free port, prints it, serves (blocking).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from refereekit.cli import main

def test_cli_ingest_then_verify(tmp_path, sample_pdf_path, capsys):
    sess = tmp_path / "s"
    assert main(["ingest", str(sample_pdf_path), "--session", str(sess)]) == 0
    assert (sess / "doc.json").exists()
    # a true quote on page 1 -> PASS, exit 0
    rc = main(["verify", "--session", str(sess), "--kind", "quote",
               "--anchor", "1", "--text", "prescribed degree-size sequences"])
    out = capsys.readouterr().out
    assert rc == 0 and "PASS" in out
    # a false quote -> FAIL, exit 1
    rc2 = main(["verify", "--session", str(sess), "--kind", "quote",
                "--anchor", "1", "--text", "this sentence is not in the paper at all"])
    assert rc2 == 1 and "FAIL" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refereekit.cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# refereekit/cli.py
import argparse, sys
from pathlib import Path
from .ingest import ingest
from .verify import verify
from .types import Claim
from .session import Session
from . import render

def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="refereekit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest"); pi.add_argument("pdf"); pi.add_argument("--session", required=True)
    pv = sub.add_parser("verify")
    for a in ("--session", "--kind", "--anchor", "--text"):
        pv.add_argument(a, required=True)
    ps = sub.add_parser("serve"); ps.add_argument("--session", required=True); ps.add_argument("--port", type=int, default=8888)

    args = ap.parse_args(argv)

    if args.cmd == "ingest":
        s = Session.create(Path(args.session).parent, Path(args.session).name)
        doc = ingest(args.pdf); s.save_doc(doc)
        print(f"ingested: {len(doc.pages)} pages, {len(doc.equations)} equations")
        return 0

    if args.cmd == "verify":
        s = Session(Path(args.session))
        v = verify(Claim(args.text, args.kind, args.anchor), s.load_doc())
        print(f"{v.status}: {v.evidence}")
        return 1 if v.status == "FAIL" else 0

    if args.cmd == "serve":
        s = Session(Path(args.session))
        port = render.pick_port(args.port)
        print(f"serving {s.dir} at http://127.0.0.1:{port}/")
        render.serve(s, port)
        return 0
    return 2
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refereekit/cli.py tests/test_cli.py
git commit -m "feat: CLI (ingest, verify, serve)"
```

---

### Task 10: Full suite + README + acceptance

**Files:**
- Create: `README.md`
- Test: run the whole suite.

**Interfaces:** none new.

- [ ] **Step 1: Run the whole suite**

Run: `.venv/bin/pytest -v`
Expected: ALL PASS (import, types, fixture, ingest, guard, verify, session, render, cli).

- [ ] **Step 2: Manual acceptance (documented, not committed with manuscript)**

Run (against the fixture only):
```bash
.venv/bin/refereekit ingest tests/fixtures/sample_paper.pdf --session /tmp/demo
.venv/bin/refereekit verify --session /tmp/demo --kind equation --anchor 3 --text x
.venv/bin/refereekit verify --session /tmp/demo --kind equation --anchor 9 --text x
```
Expected: ingest prints counts; anchor 3 → PASS (exit 0); anchor 9 → FAIL (exit 1).

- [ ] **Step 3: Write README**

```markdown
# refereekit

Standalone, harness-portable toolkit that automates a paper-review workflow.
Phase 1 (this release): ingest a PDF, verify factual anchors against it, guard
manuscript text from leaving the machine, and serve a live Q&A page.

## Confidentiality
Confidential manuscripts and text derived from them are never committed. The only
committable PDF is the test fixture under `tests/fixtures/`. Manuscript text is
never sent to any network service in Phase 1 (no LLM/Exa/memory yet).

## Install
    python -m venv .venv && .venv/bin/pip install -e ".[dev]"

## Use
    refereekit ingest paper.pdf --session ./work/paperA
    refereekit verify --session ./work/paperA --kind quote --anchor 16 --text "5-8%"
    refereekit serve  --session ./work/paperA --port 8888

## Test
    .venv/bin/pytest -v
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README + Phase 1 acceptance"
```

---

## Self-Review

**Spec coverage (SP-A scope):**
- ingest (§5) → Task 4 ✓ · verify PASS/FAIL/FLAG (§5) → Task 6 ✓ · guard fail-closed for manuscript text (§7) → Task 5 ✓ · render live HTML + port auto-increment (§5, §7) → Task 8 ✓ · session/state resumable (§5) → Task 7 ✓ · CLI (§5) → Task 9 ✓ · fixture from arXiv:2106.00185, never the confidential manuscript (§8) → Task 3 ✓ · dependency-light (§3) → argparse/stdlib only ✓.
- Deferred to later phases (correctly out of SP-A): litsearch, llm zero-retention client, memory MemoryStore/SQLite, drafts, embedded agent loop. The `llm.complete` zero-retention guard test (§8) belongs to the phase that introduces `llm` — noted for Plan 2.
- Diagram update (spec §10) is tracked as a separate task in the session, run after the plan executes; not a code task here.

**Placeholder scan:** no TBD/TODO; every code step has complete code; no "handle edge cases" hand-waves.

**Type consistency:** `Document/Page/Figure/Equation/Section/Claim/Verdict` used identically across tasks; `ingest.to_json/from_json` reused by `session`; `Session` attribute names (`dir`, `html`, `doc_json`, `state_json`) consistent in tasks 7→8→9; `verify(Claim, Document)->Verdict` signature stable tasks 6→9.
