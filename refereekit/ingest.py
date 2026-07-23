import json, re
from pathlib import Path
import fitz  # PyMuPDF
from .types import Document, Page, Figure, Equation, Section

_BARE_INT = re.compile(r"\d{1,3}")
_FIG_LINE = re.compile(r"^\s*(?:FIG\.|Figure)\s*(\d+)\.\s*(.*)$", re.I)
_SEC_NUM = re.compile(r"^\s*(\d+(?:\.\d+)?)\.?\s+([A-Z][A-Za-z].{2,60})$")
_SEC_ROMAN = re.compile(r"^\s*(I{1,3}|IV|V|VI{0,3}|IX|X)\.\s+([A-Z].{2,60})$")

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

def _extract_figures(page_text: str, page_no: int) -> list[Figure]:
    figs, seen = [], set()
    for line in page_text.splitlines():
        m = _FIG_LINE.match(line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            figs.append(Figure(id=m.group(1), page=page_no, caption=m.group(2).strip()))
    return figs

def _extract_sections(page_text: str, page_no: int) -> list[Section]:
    secs = []
    for line in page_text.splitlines():
        s = line.strip()
        m = _SEC_NUM.match(s) or _SEC_ROMAN.match(s)
        if m:
            secs.append(Section(title=s, page=page_no))
    return secs

def ingest(pdf_path) -> Document:
    doc = fitz.open(str(pdf_path))
    pages, equations, figures, sections = [], [], [], []
    total_text = ""
    for i in range(doc.page_count):
        pg = doc[i]
        text = pg.get_text()
        total_text += text
        pages.append(Page(n=i + 1, text=text, blocks=[]))
        equations.extend(_extract_equation_numbers(pg))
        figures.extend(_extract_figures(text, i + 1))
        sections.extend(_extract_sections(text, i + 1))
    if not total_text.strip():
        raise ValueError("no extractable text")
    _seen = set(); _f = []
    for f in figures:
        if f.id not in _seen:
            _seen.add(f.id); _f.append(f)
    figures = _f
    _eq_seen = set(); _eq = []
    for e in equations:
        if e.id not in _eq_seen:
            _eq_seen.add(e.id); _eq.append(e)
    equations = _eq
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
