from dataclasses import dataclass, field
from pathlib import Path
from ..llm import complete
from ..drafts import extract_anchors
from ..verify import verify
from .. import render
from ..ingest import ingest
from ..session import Session
from .. import drafts


@dataclass
class ReviewResult:
    report_path: Path
    editor_path: Path
    flags: list = field(default_factory=list)
    verdict: dict = field(default_factory=dict)


def run_review(pdf_path, *, backend, session_dir, input_fn=input, output_fn=print,
               style_path="style/STYLE.md", memory=None, venue=None) -> ReviewResult:
    session_dir = Path(session_dir)
    session = Session.create(session_dir.parent, session_dir.name)
    doc = ingest(pdf_path)
    session.save_doc(doc)
    # 1. summarize
    summary = complete(_doc_context(doc, [], "Summarize this paper for a referee."),
                       backend=backend, manuscript_ok=True)
    output_fn("SUMMARY:\n" + summary)
    # 2. Q&A
    _qa_loop(session, doc, backend=backend, input_fn=input_fn, output_fn=output_fn)
    # 3. verdict gate
    verdict = _verdict_gate(session, input_fn=input_fn, output_fn=output_fn)
    # 4. draft
    lengths = _detail_gate(input_fn=input_fn)
    rep = drafts.report(session, verdict, lengths, backend=backend,
                        style_path=style_path, memory=memory, venue=venue)
    report_path = session_dir / "report.txt"
    report_path.write_text(rep.text)
    # 5-6. editor
    answers = _editor_answers(input_fn=input_fn)
    ed = drafts.editor_letter(session, answers, backend=backend,
                              style_path=style_path, memory=memory, venue=venue)
    editor_path = session_dir / "editor.txt"
    editor_path.write_text(ed.text)
    return ReviewResult(report_path=report_path, editor_path=editor_path,
                        flags=rep.flags + ed.flags, verdict=verdict)


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
