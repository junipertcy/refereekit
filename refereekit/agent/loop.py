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
