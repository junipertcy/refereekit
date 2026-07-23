import json, re
from pathlib import Path
import fitz  # PyMuPDF
from .types import Document, Page, Figure, Equation, Section

_EQ_LABEL = re.compile(r"\((\d{1,3})\)\s*$")
_FIG_LINE = re.compile(r"^\s*FIG\.\s*(\d+)\.\s*(.*)$")

def _extract_figures(page_text: str, page_no: int) -> list[Figure]:
    figs, seen = [], set()
    for line in page_text.splitlines():
        m = _FIG_LINE.match(line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            figs.append(Figure(id=m.group(1), page=page_no, caption=m.group(2).strip()))
    return figs

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
        figures.extend(_extract_figures(text, i + 1))
    if not total_text.strip():
        raise ValueError("no extractable text")
    _seen = set(); _f = []
    for f in figures:
        if f.id not in _seen:
            _seen.add(f.id); _f.append(f)
    figures = _f
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
