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
from .spec import load_spec, scripted_input
from .policy import assert_llm_permitted, VenuePolicyError

# Default style guide path (repo root / style / STYLE.md)
_DEFAULT_STYLE = Path(__file__).resolve().parent.parent / "style" / "STYLE.md"

# Per-transport model defaults. Bedrock names a model differently from the
# first-party API, so one default cannot serve both.
_DEFAULT_MODEL = {"anthropic": "claude-opus-4-8", "bedrock": "anthropic.claude-opus-5"}


def _backend():
    from .llm import FakeBackend
    if os.environ.get("REFEREEKIT_FAKE") == "1":
        return FakeBackend(os.environ.get("REFEREEKIT_FAKE_TEXT", "draft"))
    transport = os.environ.get("REFEREEKIT_BACKEND", "anthropic")
    if transport not in _DEFAULT_MODEL:
        raise ValueError(
            f"unknown REFEREEKIT_BACKEND {transport!r}; "
            f"expected one of {', '.join(sorted(_DEFAULT_MODEL))}"
        )
    # The attestation is about the account, not the transport, so it is read
    # once and threaded into whichever backend is built.
    zero_retention = os.environ.get("REFEREEKIT_ZERO_RETENTION") == "1"
    model = os.environ.get("REFEREEKIT_MODEL") or _DEFAULT_MODEL[transport]
    if transport == "bedrock":
        from .llm import BedrockBackend
        return BedrockBackend(
            model=model,
            zero_retention=zero_retention,
            region=os.environ.get("AWS_REGION", "us-east-1"),
        )
    from .llm import AnthropicBackend
    return AnthropicBackend(model=model, zero_retention=zero_retention)

def _session_venue(session) -> str | None:
    """The venue this session belongs to, however it was recorded.

    or-fetch writes it at the top level; run_review writes it inside the verdict
    it saves. Either is authoritative, so a command that did not take --venue can
    still tell which venue's rules apply.
    """
    return (session.get_state("venue")
            or (session.get_state("verdict") or {}).get("venue"))


def _write_draft(session, name, draft):
    d = session.ours_dir
    (d / f"{name}.txt").write_text(draft.text)
    print(f"{name}: wrote {len(draft.text)} chars, {len(draft.flags)} flag(s)")
    for f in draft.flags:
        print(f"  FLAG {f.kind} ({f.anchor}): {f.reason}")

def _blank_span(f) -> str:
    """The short column describing a field the referee fills in.

    A numeric enum has a low-high span, and the invitation does not promise an
    order, so it is derived from min and max rather than the first and last
    entries. A textual enum has no span at all: printing '(I agree-I agree)'
    would read as a range that does not exist, so its options are listed and
    truncated to keep the column aligned.
    """
    if not f.enum:
        return f"({f.type})"
    values = [v for v, _ in f.enum]
    if all(isinstance(v, (int, float)) and not isinstance(v, bool)
           for v in values):
        return f"({min(values)}-{max(values)})"
    joined = "|".join(str(v) for v in values)
    return f"({joined[:20]}...)" if len(joined) > 20 else f"({joined})"

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
    prv.add_argument("--spec", help="TOML review spec; drives every gate "
                                    "without typed input")
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
    pod.add_argument("--db")
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
            # Before _backend(): the session records its venue, so the venue's
            # rule about outside models is knowable without --venue here.
            assert_llm_permitted(_session_venue(s))
            lengths = dict(x.split("=", 1) for x in args.length)
            # Choose style path: --style arg > REFEREEKIT_STYLE env > default
            style_path = args.style or os.environ.get("REFEREEKIT_STYLE") or str(_DEFAULT_STYLE)
            d = drafts.report(s, s.get_state("verdict", {}), lengths,
                              backend=_backend(), style_path=style_path)
            _write_draft(s, "report", d); return 0
        except (FileNotFoundError, ValueError, RetentionError, VenuePolicyError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "editor":
        try:
            from . import drafts
            from .llm import RetentionError
            s = Session(Path(args.session))
            assert_llm_permitted(_session_venue(s))
            answers = dict(x.split("=", 1) for x in args.answers)
            # Choose style path: --style arg > REFEREEKIT_STYLE env > default
            style_path = args.style or os.environ.get("REFEREEKIT_STYLE") or str(_DEFAULT_STYLE)
            d = drafts.editor_letter(s, answers, backend=_backend(), style_path=style_path)
            _write_draft(s, "editor", d); return 0
        except (FileNotFoundError, ValueError, RetentionError, VenuePolicyError) as e:
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
            # Parsed first, before the backend is built and before any page of
            # the manuscript is read: a spec that cannot drive the run must fail
            # while nothing has been sent anywhere.
            spec = load_spec(args.spec) if args.spec else None
            kwargs = {"input_fn": scripted_input(spec)} if spec else {}
            venue = args.venue or (spec.venue if spec else None)
            # Before the PDF is opened and before a backend exists.
            assert_llm_permitted(venue)
            sdir = Path(args.session)
            db = args.db or str(sdir / "memory.db")
            if venue:
                sdir.mkdir(parents=True, exist_ok=True)  # ensure db parent exists
            mem = SQLiteMemoryStore(db) if venue else None
            # Style path: --style arg > REFEREEKIT_STYLE env > default (same as draft/editor).
            # Use the location-anchored default so `review` works from any cwd, not just repo root.
            style_path = args.style or os.environ.get("REFEREEKIT_STYLE") or str(_DEFAULT_STYLE)
            res = run_review(args.pdf, backend=_backend(), session_dir=sdir,
                           style_path=style_path, memory=mem, venue=venue,
                           **kwargs)
        except (FileNotFoundError, ValueError, RetentionError, VenuePolicyError, ManuscriptLeakError, sqlite3.OperationalError, pymupdf.FileNotFoundError, EOFError) as e:
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
                found, unreadable = orclient.list_assignments(c, args.venue)
                if not found:
                    print(f"no assignments for you at {args.venue}")
                for a in found:
                    print(f"  {a.number:>4}  {a.title}")
                if unreadable:
                    # Usually a withdrawn or desk-rejected paper still carrying
                    # an assignment edge. Named so the referee knows the list is
                    # short rather than believing it is complete.
                    print(f"could not read {len(unreadable)} assigned "
                          f"submission(s): {', '.join(unreadable)}")
                if found:
                    print("Fetch one with: --number <N>")
                return 0
            sdir = Path(args.session)
            # Checked before Session.create, which is exist_ok: fetching a
            # second paper into a session would overwrite paper.pdf, doc.json
            # and form.json, leave theirs/ holding both papers' notes, and
            # leave a stale ours/openreview.md that or-responses would read as
            # our review of the new paper. put_theirs cannot catch it because
            # the filenames are legitimately distinct. Re-fetching the same
            # number is the normal way to pick up a new rebuttal.
            had = Session(sdir).get_state("number")
            if had is not None and had != args.number:
                raise ValueError(
                    f"session {sdir} holds submission {had}, not {args.number}; "
                    f"use a fresh --session directory for a different paper")
            s = Session.create(sdir.parent, sdir.name)
            pdf_bytes, forum = orclient.fetch_submission(c, args.venue, args.number)
            # pymupdf sniffs the content type, so an html error page opens as an
            # html document and ingests as one page of text rather than raising.
            # Only the magic bytes distinguish that from a real paper, and a
            # session built from an error page would pass for a fetched one.
            if not pdf_bytes.startswith(b"%PDF"):
                raise ValueError(
                    f"the download for submission {args.number} is not a pdf "
                    f"({len(pdf_bytes)} bytes); no paper.pdf was written")
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
            form, why = orclient.fetch_form(c, args.venue, args.number)
            if form is None:
                # The reason distinguishes an unopened review stage from a 503
                # or an expired token, which used to print the same line and
                # send the referee to re-run the or-fetch they had just run.
                print(f"no review form at {args.venue}/Submission"
                      f"{args.number}/-/Official_Review ({why}); "
                      f"skipping form.json")
            else:
                (s.dir / "form.json").write_text(orform.to_json(form))
                s.set_state("invitation_id", form.invitation_id)
                # The same count or-draft prints under the same phrase: choices
                # plus the fields that are neither prose nor choice, since the
                # referee fills those in too.
                blanks = len(form.choice_fields()) + len(form.other_fields())
                print(f"review form: {len(form.prose_fields())} prose field(s), "
                      f"{blanks} to fill in yourself")
            replies, why = orclient.fetch_replies(c, forum)
            if why:
                print(f"could not read the discussion for {forum} ({why}); "
                      f"theirs/ left empty")
            elif not replies:
                print("no replies yet; theirs/ left empty")
            else:
                mine = orclient.our_group_ids(c, args.venue, args.number)
                written, skipped, held = orclient.store_replies(s, replies, mine)
                print(f"theirs/: {len(written)} new, {len(skipped)} unchanged"
                      + (f", {len(held)} held back" if held else ""))
                if held:
                    # theirs/ means received from others, and or-responses feeds
                    # all of it to the model as what came back. Confusing our
                    # own review for a co-referee's is the failure this feature
                    # most has to avoid, so an unresolvable signature is named
                    # rather than guessed at.
                    print("could not confirm these are not your own review, so "
                          "they were not stored in theirs/:")
                    for name in held:
                        print(f"  {name}")
                    print(f"check them by hand on forum {forum}")
            return 0
        except (orclient.ORError, FileNotFoundError, ValueError,
                ProvenanceError, pymupdf.FileNotFoundError,
                pymupdf.FileDataError) as e:
            # FileDataError: the bytes start with %PDF but the pdf is malformed,
            # a truncated download being the usual cause. Bytes that are not a
            # pdf at all are rejected by the %PDF check above, which pymupdf
            # would not catch because it sniffs the content type. EmptyFileError
            # subclasses this, so a zero-byte download lands here too.
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "or-draft":
        from .llm import RetentionError
        from .openreview import fill as orfill
        from .openreview import form as orform
        try:
            s = Session(Path(args.session))
            # First, before the form is read and well before a backend exists:
            # or-fetch recorded the venue, so the venue's own rule about outside
            # models is knowable here without the referee restating it.
            assert_llm_permitted(s.get_state("venue"))
            form_path = s.dir / "form.json"
            if not form_path.exists():
                print("error: no form.json; run or-fetch --number first",
                      file=sys.stderr)
                return 2
            form = orform.from_json(form_path.read_text())
            style_path = (args.style or os.environ.get("REFEREEKIT_STYLE")
                          or str(_DEFAULT_STYLE))
            # Parsed on its own line, before _backend(): keyword arguments
            # evaluate left to right, so building the backend inside the call
            # would run it before this input error could be reported.
            try:
                lengths = dict(x.split("=", 1) for x in args.length)
            except ValueError:
                print("error: --length takes name=value, "
                      "e.g. --length summary=short", file=sys.stderr)
                return 2
            # Before _backend() for the same reason: an unknown field name and
            # a session with no claim pool are both input errors, and the
            # referee needs the typo or the next command rather than a report
            # about their install.
            orfill.validate_lengths(form, lengths)
            orfill.validate_pool(s)
            # The venue or-fetch recorded, so the accumulated voice and verdict
            # patterns for it reach the draft, exactly as they do under review.
            # Same --db default as review, which is where the review pass this
            # session required will have written them.
            venue = s.get_state("venue")
            db = args.db or str(s.dir / "memory.db")
            mem = SQLiteMemoryStore(db) if venue else None
            backend = _backend()
            filled = orfill.fill(s, form, backend=backend,
                                 style_path=style_path, lengths=lengths,
                                 memory=mem, venue=venue)
            s.our_draft("openreview.md").write_text(orfill.to_markdown(form, filled))
            s.our_draft("openreview.json").write_text(orfill.to_json(filled))
            print(f"openreview: {len(filled.values)} prose field(s) drafted, "
                  f"{len(filled.flags)} flag(s)")
            for f in filled.flags:
                print(f"  FLAG {f.kind} ({f.anchor}): {f.reason}")
            print("to fill in yourself:")
            for f in filled.blanks:
                print(f"  {f.name:<24} {_blank_span(f):<10} {f.description[:48]}")
            return 0
        except (FileNotFoundError, ValueError, RetentionError, VenuePolicyError,
                sqlite3.OperationalError, ImportError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "or-responses":
        from .llm import RetentionError
        from .openreview import responses as orresponses
        try:
            s = Session(Path(args.session))
            # A typo in --session is the usual cause, and it needs its own
            # message. Reported before reading theirs/, and reached as a plain
            # path rather than through the theirs_dir property, because that
            # property mkdirs: diagnosing a missing session must not create it.
            if not s.dir.exists():
                print(f"error: no session at {s.dir}; run or-fetch --number "
                      f"first", file=sys.stderr)
                return 2
            theirs = s.dir / "theirs"
            received = ([p.read_text() for p in sorted(theirs.iterdir())
                         if p.is_file()] if theirs.exists() else [])
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
        except (FileNotFoundError, ValueError, RetentionError,
                ImportError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    return 2
