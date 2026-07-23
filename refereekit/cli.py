# refereekit/cli.py
import argparse, sys, os, sqlite3
from pathlib import Path
import pymupdf
from .ingest import ingest
from .verify import verify
from .types import Claim
from .session import Session
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
    d = session.dir / "drafts"; d.mkdir(parents=True, exist_ok=True)
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
            return 1 if v.status == "FAIL" else 0
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

    return 2
