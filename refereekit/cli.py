# refereekit/cli.py
import argparse, sys, os, sqlite3
from pathlib import Path
import pymupdf
from .ingest import ingest
from .verify import verify
from .types import Claim
from .session import Session, ProvenanceError
from . import render
from .memory import SQLiteMemoryStore, Note
from .guard import ManuscriptLeakError
from .agent import run_review

# Default style guide path (repo root / style / STYLE.md)
_DEFAULT_STYLE = Path(__file__).resolve().parent.parent / "style" / "STYLE.md"

def _backend():
    from .llm import FakeBackend
    if os.environ.get("REFEREEKIT_FAKE") == "1":
        return FakeBackend(os.environ.get("REFEREEKIT_FAKE_TEXT", "draft"))
    from .llm import AnthropicBackend
    return AnthropicBackend(
        model=os.environ.get("REFEREEKIT_MODEL", "claude-opus-4-8"),
        zero_retention=os.environ.get("REFEREEKIT_ZERO_RETENTION") == "1",
    )

def _write_draft(session, name, draft):
    d = session.ours_dir
    (d / f"{name}.txt").write_text(draft.text)
    print(f"{name}: wrote {len(draft.text)} chars, {len(draft.flags)} flag(s)")
    for f in draft.flags:
        print(f"  FLAG {f.kind} ({f.anchor}): {f.reason}")

def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="refereekit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest"); pi.add_argument("pdf"); pi.add_argument("--session", required=True)
    pv = sub.add_parser("verify")
    for a in ("--session", "--kind", "--anchor", "--text"):
        pv.add_argument(a, required=True)
    ps = sub.add_parser("serve"); ps.add_argument("--session", required=True); ps.add_argument("--port", type=int, default=8888)
    pd = sub.add_parser("draft"); pd.add_argument("--session", required=True)
    pd.add_argument("--length", action="append", default=[])
    pd.add_argument("--style", default=None)
    pe = sub.add_parser("editor"); pe.add_argument("--session", required=True)
    pe.add_argument("--answers", action="append", default=[])
    pe.add_argument("--style", default=None)
    pms = sub.add_parser("mem-store")
    for a in ("--session", "--venue", "--kind", "--text"): pms.add_argument(a, required=True)
    pms.add_argument("--db")
    pmr = sub.add_parser("mem-recall")
    pmr.add_argument("--venue", required=True); pmr.add_argument("--db", required=True)
    pmr.add_argument("--limit", type=int, default=20)
    prv = sub.add_parser("review")
    prv.add_argument("pdf")
    prv.add_argument("--session", required=True)
    prv.add_argument("--venue")
    prv.add_argument("--db")
    prv.add_argument("--style", default=None)
    pof = sub.add_parser("or-fetch")
    pof.add_argument("--venue", required=True)
    pof.add_argument("--session", required=True)
    pof.add_argument("--number", type=int)
    pof.add_argument("--baseurl", default=None)
    pod = sub.add_parser("or-draft")
    pod.add_argument("--session", required=True)
    pod.add_argument("--length", action="append", default=[])
    pod.add_argument("--style", default=None)
    por = sub.add_parser("or-responses")
    por.add_argument("--session", required=True)

    args = ap.parse_args(argv)

    if args.cmd == "ingest":
        try:
            s = Session.create(Path(args.session).parent, Path(args.session).name)
            doc = ingest(args.pdf); s.save_doc(doc)
            print(f"ingested: {len(doc.pages)} pages, {len(doc.equations)} equations")
            return 0
        except (FileNotFoundError, ValueError, pymupdf.FileNotFoundError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "verify":
        try:
            s = Session(Path(args.session))
            v = verify(Claim(args.text, args.kind, args.anchor), s.load_doc())
            print(f"{v.status}: {v.evidence}")
            if v.status == "FAIL":
                return 1
            elif v.status == "FLAG":
                return 3
            else:  # PASS
                return 0
        except (FileNotFoundError, ValueError, pymupdf.FileNotFoundError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "serve":
        s = Session(Path(args.session))
        port = render.pick_port(args.port)
        print(f"serving {s.dir} at http://127.0.0.1:{port}/")
        render.serve(s, port)
        return 0

    if args.cmd == "draft":
        try:
            from . import drafts
            from .llm import RetentionError
            s = Session(Path(args.session))
            lengths = dict(x.split("=", 1) for x in args.length)
            # Choose style path: --style arg > REFEREEKIT_STYLE env > default
            style_path = args.style or os.environ.get("REFEREEKIT_STYLE") or str(_DEFAULT_STYLE)
            d = drafts.report(s, s.get_state("verdict", {}), lengths,
                              backend=_backend(), style_path=style_path)
            _write_draft(s, "report", d); return 0
        except (FileNotFoundError, ValueError, RetentionError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "editor":
        try:
            from . import drafts
            from .llm import RetentionError
            s = Session(Path(args.session))
            answers = dict(x.split("=", 1) for x in args.answers)
            # Choose style path: --style arg > REFEREEKIT_STYLE env > default
            style_path = args.style or os.environ.get("REFEREEKIT_STYLE") or str(_DEFAULT_STYLE)
            d = drafts.editor_letter(s, answers, backend=_backend(), style_path=style_path)
            _write_draft(s, "editor", d); return 0
        except (FileNotFoundError, ValueError, RetentionError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "mem-store":
        s = Session(Path(args.session))
        db = args.db or str(s.dir / "memory.db")
        try:
            doc = s.load_doc()
            SQLiteMemoryStore(db).store(Note(args.text, args.venue, args.kind), doc)
        except (FileNotFoundError, ValueError, sqlite3.OperationalError, ManuscriptLeakError) as e:
            print(f"mem-store failed: {e}", file=sys.stderr); return 2
        print(f"stored note for {args.venue}"); return 0

    if args.cmd == "mem-recall":
        try:
            notes = SQLiteMemoryStore(args.db).recall(args.venue, args.limit)
            for nt in notes: print(f"[{nt.venue}/{nt.kind}] {nt.text}")
            return 0
        except (FileNotFoundError, ValueError, sqlite3.OperationalError, ManuscriptLeakError) as e:
            print(f"mem-recall failed: {e}", file=sys.stderr)
            return 2

    if args.cmd == "review":
        try:
            from .llm import RetentionError
            sdir = Path(args.session)
            db = args.db or str(sdir / "memory.db")
            if args.venue:
                sdir.mkdir(parents=True, exist_ok=True)  # ensure db parent exists
            mem = SQLiteMemoryStore(db) if args.venue else None
            # Style path: --style arg > REFEREEKIT_STYLE env > default (same as draft/editor).
            # Use the location-anchored default so `review` works from any cwd, not just repo root.
            style_path = args.style or os.environ.get("REFEREEKIT_STYLE") or str(_DEFAULT_STYLE)
            res = run_review(args.pdf, backend=_backend(), session_dir=sdir,
                           style_path=style_path, memory=mem, venue=args.venue)
        except (FileNotFoundError, ValueError, RetentionError, ManuscriptLeakError, sqlite3.OperationalError, pymupdf.FileNotFoundError, EOFError) as e:
            print(f"review failed: {e}", file=sys.stderr)
            return 2
        print(f"review complete: {res.report_path}, {res.editor_path} ({len(res.flags)} flag(s))")
        return 0

    if args.cmd == "or-fetch":
        from .openreview import client as orclient
        from .openreview import form as orform
        try:
            c = orclient.make_client(args.baseurl or orclient.BASEURL)
            if args.number is None:
                found = orclient.list_assignments(c, args.venue)
                if not found:
                    print(f"no assignments for you at {args.venue}")
                    return 0
                for a in found:
                    print(f"  {a.number:>4}  {a.title}")
                print("Fetch one with: --number <N>")
                return 0
            sdir = Path(args.session)
            s = Session.create(sdir.parent, sdir.name)
            pdf_bytes, forum = orclient.fetch_submission(c, args.venue, args.number)
            # pymupdf sniffs the content type, so an html error page opens as an
            # html document and ingests as one page of text rather than raising.
            # Only the magic bytes distinguish that from a real paper, and a
            # session built from an error page would pass for a fetched one.
            if not pdf_bytes.startswith(b"%PDF"):
                raise ValueError(
                    f"the download for submission {args.number} is not a pdf "
                    f"({len(pdf_bytes)} bytes); nothing was written")
            pdf_path = s.dir / "paper.pdf"
            pdf_path.write_bytes(pdf_bytes)
            doc = ingest(pdf_path)
            s.save_doc(doc)
            print(f"fetched submission {args.number}: {len(doc.pages)} pages")
            s.set_state("venue", args.venue)
            s.set_state("number", args.number)
            s.set_state("forum", forum)
            # Best-effort from here. Before the review stage opens there is no
            # invitation, and before the rebuttal period there are no replies.
            # Neither is an error: the pdf is the part the referee needs first.
            form = orclient.fetch_form(c, args.venue, args.number)
            if form is None:
                print(f"no review form yet at {args.venue}/Submission"
                      f"{args.number}/-/Official_Review; skipping form.json")
            else:
                (s.dir / "form.json").write_text(orform.to_json(form))
                s.set_state("invitation_id", form.invitation_id)
                print(f"review form: {len(form.prose_fields())} prose field(s), "
                      f"{len(form.choice_fields())} to fill in yourself")
            replies = orclient.fetch_replies(c, forum)
            if not replies:
                print("no replies yet; theirs/ left empty")
            else:
                mine = orclient.our_group_ids(c, args.venue, args.number)
                written, skipped = orclient.store_replies(s, replies, mine)
                print(f"theirs/: {len(written)} new, {len(skipped)} unchanged")
            return 0
        except (orclient.ORError, FileNotFoundError, ValueError,
                ProvenanceError, pymupdf.FileNotFoundError,
                pymupdf.FileDataError) as e:
            # FileDataError: the download returned bytes that are not a PDF.
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "or-draft":
        from .llm import RetentionError
        from .openreview import fill as orfill
        from .openreview import form as orform
        try:
            s = Session(Path(args.session))
            form_path = s.dir / "form.json"
            if not form_path.exists():
                print("error: no form.json; run or-fetch --number first",
                      file=sys.stderr)
                return 2
            form = orform.from_json(form_path.read_text())
            style_path = (args.style or os.environ.get("REFEREEKIT_STYLE")
                          or str(_DEFAULT_STYLE))
            filled = orfill.fill(s, form, backend=_backend(),
                                 style_path=style_path,
                                 lengths=dict(x.split("=", 1) for x in args.length))
            s.our_draft("openreview.md").write_text(orfill.to_markdown(form, filled))
            s.our_draft("openreview.json").write_text(orfill.to_json(filled))
            print(f"openreview: {len(filled.values)} prose field(s) drafted, "
                  f"{len(filled.flags)} flag(s)")
            for f in filled.flags:
                print(f"  FLAG {f.kind} ({f.anchor}): {f.reason}")
            print("to fill in yourself:")
            for f in filled.blanks:
                span = (f"({f.enum[-1][0]}-{f.enum[0][0]})" if f.enum else f"({f.type})")
                print(f"  {f.name:<24} {span:<10} {f.description[:48]}")
            return 0
        except (FileNotFoundError, ValueError, RetentionError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "or-responses":
        from .llm import RetentionError
        from .openreview import responses as orresponses
        try:
            s = Session(Path(args.session))
            received = [p.read_text() for p in sorted(s.theirs_dir.iterdir())
                        if p.is_file()]
            # Checked before constructing a backend: an empty theirs/ is an
            # input error, and it should not first fail on a missing API key.
            if not received:
                print("error: no received notes in theirs/; nothing to analyze",
                      file=sys.stderr)
                return 2
            ours = ""
            for name in ("openreview.md", "report.txt"):
                p = s.ours_dir / name
                if p.exists():
                    ours = p.read_text()
                    break
            text = orresponses.analyze(ours, received, backend=_backend())
            out = s.our_draft("response-analysis.txt")
            out.write_text(text)
            print(f"wrote {out} ({len(received)} received note(s))")
            return 0
        except (FileNotFoundError, ValueError, RetentionError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    return 2
