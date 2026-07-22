# refereekit/cli.py
import argparse, sys
from pathlib import Path
from .ingest import ingest
from .verify import verify
from .types import Claim
from .session import Session
from . import render

def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="refereekit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest"); pi.add_argument("pdf"); pi.add_argument("--session", required=True)
    pv = sub.add_parser("verify")
    for a in ("--session", "--kind", "--anchor", "--text"):
        pv.add_argument(a, required=True)
    ps = sub.add_parser("serve"); ps.add_argument("--session", required=True); ps.add_argument("--port", type=int, default=8888)

    args = ap.parse_args(argv)

    if args.cmd == "ingest":
        s = Session.create(Path(args.session).parent, Path(args.session).name)
        doc = ingest(args.pdf); s.save_doc(doc)
        print(f"ingested: {len(doc.pages)} pages, {len(doc.equations)} equations")
        return 0

    if args.cmd == "verify":
        s = Session(Path(args.session))
        v = verify(Claim(args.text, args.kind, args.anchor), s.load_doc())
        print(f"{v.status}: {v.evidence}")
        return 1 if v.status == "FAIL" else 0

    if args.cmd == "serve":
        s = Session(Path(args.session))
        port = render.pick_port(args.port)
        print(f"serving {s.dir} at http://127.0.0.1:{port}/")
        render.serve(s, port)
        return 0
    return 2
