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
