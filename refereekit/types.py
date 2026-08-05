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

# A quotation shorter than this cannot be evidence: short strings collide by
# accident, and the empty string is a substring of every page. Claims below
# this floor verify as FLAG (unverifiable), never PASS. See verify().
MIN_EVIDENCE_WORDS = 4
