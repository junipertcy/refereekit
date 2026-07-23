from ..llm import complete
from ..drafts import extract_anchors
from ..verify import verify
from .. import render


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
