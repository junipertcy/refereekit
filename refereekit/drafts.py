import re
from dataclasses import dataclass, field
from .types import Claim
from .verify import verify
from .llm import complete
from .style import load_style

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
        "Cite page/equation anchors only if they appear in the verified claims above.\n\n"
        "=== CITATION FORMAT ===\n"
        "When citing pages and equations, use ONLY these forms:\n"
        "- Page citations: 'p. N' (e.g., 'p. 16')\n"
        "- Equation citations: 'Eq. (N)' with parentheses (e.g., 'Eq. (3)')\n"
        "Use no other citation style or format."
    )

def _verify_prose(prose: str, pool: dict, doc) -> Draft:
    """Extract anchors from generated prose and flag any that are not in the
    verified pool or fail re-verification. Shared by report() and editor_letter()
    so the anchor-integrity guarantee has a single source of truth."""
    pool_keys = {(c.kind, c.anchor) for c in pool["claims"]}
    flags = []
    for a in extract_anchors(prose):
        if (a.kind, a.anchor) not in pool_keys:
            flags.append(Flag(a.anchor, a.kind, "not in verified pool"))
        elif verify(a, doc).status != "PASS":
            flags.append(Flag(a.anchor, a.kind, "failed re-verification"))
    return Draft(text=prose, flags=flags)

def report(session, verdict: dict, section_lengths: dict, *, backend, style_path) -> Draft:
    pool = build_pool(session)
    prompt = build_prompt(pool, load_style(style_path), section_lengths)
    prose = complete(prompt, backend=backend, manuscript_ok=True)
    return _verify_prose(prose, pool, session.load_doc())

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
        f"=== VERIFIED CLAIMS (cite ONLY these anchors) ===\n{claim_lines}\n\n"
        "Cite page/equation anchors only if they appear in the verified claims above.\n\n"
        "=== CITATION FORMAT ===\n"
        "When citing pages and equations, use ONLY these forms:\n"
        "- Page citations: 'p. N' (e.g., 'p. 16')\n"
        "- Equation citations: 'Eq. (N)' with parentheses (e.g., 'Eq. (3)')\n"
        "Use no other citation style or format."
    )

def editor_letter(session, answers: dict, *, backend, style_path) -> Draft:
    pool = build_pool(session)
    prompt = build_editor_prompt(pool, load_style(style_path), answers)
    prose = complete(prompt, backend=backend, manuscript_ok=True)
    return _verify_prose(prose, pool, session.load_doc())
