# The tools on their own

`review` runs the whole pipeline in one command, but the five pieces
underneath it — `ingest`, `verify`, `serve`, `draft`, and `editor` — are
each their own command too, and none needs the other four to run. Reach
for one alone when you already have a quotation to check, want to read a
session's rendered page without re-answering questions, or need a report
or letter redrafted without re-running the loop that built the session in
the first place. This page walks through those three situations; [the
command reference](../reference/cli.md) has every flag each command
accepts.

## Check a quotation against a page: `ingest` then `verify`

You have a sentence — something you are about to write into a report, or
something a co-referee sent you — and you want to know whether it really
is on the page it claims, without running the whole review pipeline to
get there. `ingest` reads the PDF once and extracts its pages, equations
and figures into the session; `verify` then checks as many claims against
that extraction as you like, at no further cost, because it never reopens
the PDF.

```bash
refereekit ingest tests/fixtures/real_paper.pdf --session work/ref
```

```text
ingested: 9 pages, 20 equations
```

Nothing else exists in the session yet — no `state.json`, no
`index.html` — those are written by `review`'s loop, not by `ingest`; see
[The session directory](../reference/session.md#layout) for what each
command leaves behind. `verify` only needs `doc.json`, so it works
straight away:

```bash
refereekit verify --session work/ref --kind quote --anchor 1 --text "a finite set of nodes"
```

```text
PASS: found on page 1
```

The same words, claimed for a page that does not have them:

```bash
refereekit verify --session work/ref --kind quote --anchor 3 --text "words that are not on that page"
```

```text
FAIL: not found on page 3
```

And a page that is real, with words too short to check — `verify` never
returns PASS below four words, on a `quote` or `page` claim either way:

```bash
refereekit verify --session work/ref --kind page --anchor 2 --text "model"
```

```text
FLAG: page 2 exists; no quotation to verify: 1 words, need 4
```

Each verdict maps to its own exit code — 0 for PASS, 1 for FAIL, 3 for
FLAG — so a script can branch on `$?` (`$status` in fish) instead of
parsing the printed line; the full table, shared by every command, is in
[Command reference](../reference/cli.md#exit-codes). `--kind` accepts
`quote` and `page` — the same check either way, since `--anchor` is a
page number for both — plus `equation` and `figure`. `figure` checks
only that the anchor was extracted at all; `equation` checks the same
for a non-numeric id such as `2.1`, but a plain number must also fall
inside the contiguous run of extracted numbers starting at 1 —
extraction picks up page-margin noise alongside real labels, so a
number found outside that run still FAILs, not PASSes, even though it
really was extracted:

```bash
refereekit verify --session work/ref --kind equation --anchor 18 --text ""
```

```text
FAIL: equation (18) is outside the range extraction can vouch for (1-7)
```

Any other `--kind` always comes back FLAG, because refereekit has no
mechanical way to check it. Why the run exists, and what each verdict
actually promises, precisely, is [What verification
means](../concepts/verification.md#extraction-limits).

## Read the rendered page: `serve`

Reach for `serve` when you want to read a session's questions and
answers as a typeset page instead of scrolling through `state.json`'s
raw JSON, or when you want to show someone else what refereekit has
produced so far. It serves the session directory as static files and
runs until you stop it.

```bash
refereekit serve --session work/ref
```

```text
serving work/ref at http://127.0.0.1:8888/
```

`work/ref` has only been through `ingest`, so it has no `index.html` yet
— that file is written only once `review`'s question-and-answer loop
starts ([The session directory](../reference/session.md#layout)).
Opening the address above does not fail, and it does not 404 either:
`serve` is a thin wrapper over Python's own static-file server
(`refereekit/render.py`), which falls back to a directory listing when a
directory has no index file, rather than refusing outright.

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8888/
```

```text
HTTP 200
```

What you get is `doc.json` listed as a bare clickable link, not the Q&A
page you were probably after — worth knowing before you assume a 404
means the server is broken, or a 200 means the page is ready. Run
`review` on the session, or reopen the address once you have, and the
same URL becomes `index.html`, MathJax-typeset, as in [the
tutorial](../tutorial.md#3-what-landed).

Stop `serve` with Ctrl-C; it does not exit on its own otherwise. If port
8888 is already taken — by another `serve`, or by anything else — it
tries the next port, up to fifty times, and prints whichever one it
actually bound, so open the address the printed line gives you, not
necessarily 8888; see [Command reference](../reference/cli.md#serve).

## Redraft from a session you built by hand: `draft` and `editor`

Reach for `draft` or `editor` when you want a report or a letter from a
session that `review`'s loop never ran on — one you have only
`ingest`ed so far, or one you are redrafting after editing the style
guide, or after answering one more of the editor's questions. Both need
only `doc.json`; neither takes a `--db` flag or reads venue memory, even
for a session with a venue on record — redrafting never touches
`memory.db`. And neither refuses on an empty claim pool: instead of
stopping, they draft the prose and flag every anchor it cites, because a
session that never ran the question-and-answer loop still has a
manuscript to cite, just no claims yet checked against it
(`refereekit/drafts.py:98-124`).

These examples reuse the offline fake backend from [the
tutorial](../tutorial.md#1-set-up-the-fake-backend), so the draft comes
back at once, from the same three canned sentences:

```bash
export REFEREEKIT_FAKE=1
export REFEREEKIT_FAKE_TEXT='On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".'
```

```bash
refereekit draft --session work/ref
```

```text
report: wrote 124 chars, 3 flag(s)
  FLAG page (1): not in verified pool
  FLAG page (3): not in verified pool
  FLAG page (2): not in verified pool
```

`work/ref` never ran the question-and-answer loop, so its claim pool is
empty — there is nothing to check an anchor against, so all three
anchors the drafted text cites are flagged `not in verified pool`, in
the order they were extracted: the two quoted citations (pages 1 and 3)
first, then the bare pointer (page 2). Run the same command against a
session that did answer a question first, and only the anchors that
never verified are flagged:

```bash
refereekit draft --session work/tutorial
```

```text
report: wrote 124 chars, 1 flag(s)
  FLAG page (3): not in verified pool
```

[The tutorial's question](../tutorial.md#2-run-the-review) put page 1
and page 2 into the pool — one PASS, one FLAG, both kept — so only page
3, which failed verification when the question was checked, is flagged
here. A pool is what running the loop first buys you; skip it, as
`work/ref` did, and every citation is unearned until you check it. `not
in verified pool` is one of the two reasons `draft` and `editor` flag a
citation; the other, `failed re-verification`, means the anchor was in
the pool but no longer verifies — either the session's `doc.json`
changed under it (a later `or-fetch` re-ingested a revised paper), or
the drafting model altered the quoted words when it wrote the citation
into its own prose. See [What verification
means](../concepts/verification.md#the-two-draft-flags) for both.

`draft` takes `--length name=value`, repeatable, to shorten or lengthen
one section instead of the whole report; `editor` takes `--answers
key=value` the same way, one of the editor's lettered questions at a
time, and writes `ours/editor.txt` rather than `ours/report.txt`,
flagging citations the same way. Both flags, and every other detail —
including `--style`, which resolves the same way for every drafting
command — are in [Command reference](../reference/cli.md#draft).

## See also

- [Command reference](../reference/cli.md) — every flag each command
  accepts, its exit codes, and what it writes.
- [What verification means](../concepts/verification.md) — what a PASS,
  a FAIL, and a FLAG each actually promise.
- [Tutorial: a complete review, offline](../tutorial.md) — the same five
  pieces, run together as `review`, with a worked session to build
  first.
