from ..llm import complete
from ..drafts import extract_anchors
from ..verify import verify
from .. import render


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
