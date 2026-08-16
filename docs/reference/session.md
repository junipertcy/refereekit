# The session directory

This page lists everything that can appear inside `--session work/<name>` —
the directory every `refereekit` command that works on a paper reads or
writes — who writes each entry, and when it appears.

## Layout

```
<session>/
  paper.pdf       the submission — or-fetch only
  doc.json        the ingested manuscript — ingest, review, or-fetch
  form.json       the venue's review form — or-fetch, once the review stage is open
  state.json      claim pool, verdict and session facts — review, or-fetch
  memory.db       venue notes — review / mem-store / or-draft, when a venue is
                  known and no --db is given
  index.html      the rendered Q&A page — review only
  ours/           drafts we generated — created on the first draft
  theirs/         documents received from others (write-once) — or-fetch, on
                  the first reply received
```

Nothing above is created up front — a session starts as an empty directory,
and each entry appears only when the command that owns it first has
something to write:

- `ours/` — the first time a draft is written into it, by `draft`, `editor`,
  `review`, `or-draft`, or `or-responses` (`session.py:50-55`).
- `theirs/` — the first time `or-fetch` stores a confirmed reply
  (`session.py:57-63`); no other command writes there.
- `memory.db` — opened only when a venue is known and `--db` was not given,
  by `review` (`cli.py:222-225`), `mem-store` (`cli.py:187`), or `or-draft`
  (`cli.py:381`).
- `index.html` — written only by `review`, when its question-and-answer loop
  starts (`render.py:23-25`).
- `paper.pdf` and `form.json` — written only by `or-fetch`: the paper as
  soon as the download passes its PDF check, the form once the review stage
  is open (`cli.py:281`, `cli.py:301`).
- `doc.json` — written by `ingest`, `review`, and `or-fetch`, whichever of
  the three first reads and extracts this session's PDF.
- `state.json` — written by `review` and `or-fetch`; see below for exactly
  which key each of them sets.

## What appears when

After working through [the tutorial](../tutorial.md) — `refereekit review
tests/fixtures/real_paper.pdf --session work/tutorial`, answering its
question-and-answer loop and verdict gate — `work/tutorial` holds:

```bash
ls -R work/tutorial
```

```text
doc.json
index.html
ours
state.json

work/tutorial/ours:
editor.txt
report.txt
```

`review` on its own writes `doc.json`, `state.json`, `index.html`, and
`ours/` with the two drafts. There is no `paper.pdf`, `form.json`, or
`theirs/`, because those three come only from `or-fetch`, which this session
never ran. There is no `memory.db` either: the command above passes no
`--venue`, so at the point `review` decides whether to open one
(`cli.py:222-225`) no venue is known yet — the verdict gate later records
`venue: PRX` inside `verdict`, but that answer arrives too late to change
this run's `--db` decision.

Fetching the same submission from OpenReview instead of passing a PDF
directly adds `paper.pdf`, `form.json` (once the review stage is open), and
one file per confirmed reply under `theirs/`, plus `venue`, `number`,
`forum`, and — once a form is found — `invitation_id` inside `state.json`;
see [`or-fetch`](cli.md#or-fetch).

## state.json

`state.json` is one JSON object; every command that touches it reads the
whole file, updates its own key, and writes the whole file back
(`session.py:35-37`). These are the only keys anything writes:

| Key | Written by |
|---|---|
| `venue` | `or-fetch` (`cli.py:286`) |
| `number` | `or-fetch` (`cli.py:287`) |
| `forum` | `or-fetch` (`cli.py:288`) |
| `invitation_id` | `or-fetch`, once a review form is found (`cli.py:302`) |
| `verdict` | the verdict gate, inside `review` (`agent/loop.py:50-55`) |
| `claims` | the question-and-answer loop, inside `review` (`agent/loop.py:106-118`) |
| `qa_count` | the page renderer, during `review` (`render.py:25,32`) |

`verdict` itself carries a `venue` sub-key — whatever you type at the
verdict prompt. `draft` and `editor` both check the top-level `venue` key
first and fall back to `verdict`'s when it is absent (`cli.py:39-47`), so a
venue recorded either way still gates them.

Only an answer that verifies as `PASS` or `FLAG` joins `claims`; a `FAIL` is
reported to you in the transcript but never recorded
(`agent/loop.py:106-118`) — see [What verification
means](../concepts/verification.md) for what the three statuses mean.

```bash
python3 -m json.tool work/tutorial/state.json
```

```text
{
    "qa_count": 1,
    "claims": [
        {
            "text": "a finite set of nodes",
            "kind": "page",
            "anchor": "1"
        },
        {
            "text": "",
            "kind": "page",
            "anchor": "2"
        }
    ],
    "verdict": {
        "recommend": "minor revision",
        "venue": "PRX",
        "major_minor": "minor"
    }
}
```

The tutorial asks one question, and the reply makes three citations: p. 1 is
quoted correctly and joins the pool with its text; p. 2 is named but not
quoted, so it joins as a `FLAG`, with `text` left empty; p. 3 fails
verification outright and never reaches the pool. The run reports the last
two at the time, as `⚠ CITATION FAILED: page (3); unquoted, not verified:
page (2)`.

## ours/ and theirs/

`ours/` holds every draft you generate: `report.txt` and `editor.txt` from
`review`, `draft`, or `editor`; `openreview.md` and `openreview.json` from
`or-draft`; `response-analysis.txt` from `or-responses`. All of it is safe
to regenerate — rerunning the command that wrote a file overwrites it.

`theirs/` holds documents received from someone else: a co-referee's
report, an editor's letter, an author's rebuttal — whatever `or-fetch`
pulls from the OpenReview discussion. It is write-once (`session.py:69-77`):
storing a second file under a name already there raises `ProvenanceError`
instead of overwriting it, because a received file that could be silently
replaced would be indistinguishable from one refereekit generated itself. A
reply revised during the discussion period carries a new `tcdate`, so it
lands under a new name — `<note-id>-<tcdate>.txt`
(`openreview/client.py:271-310`) — and both versions are kept, rather than
working around write-once by force.

Why the two directories are kept apart: a co-referee's report is evidence
and our draft is not, so searching one for a phrase that lives in the other
proves nothing.

## What is manuscript-derived

Two entries are refused by name, anywhere in the repository, because
`.gitignore` matches them directly: `paper.pdf` (`.gitignore:11-13`) and
`index.html` (`.gitignore:21-24`, with one exception for
`diagrams/index.html`, which is documentation, not a session).

Everything else that can hold manuscript text or a judgement built from it —
`doc.json`, `state.json`, `ours/`, `theirs/`, `memory.db` — matches no
pattern of its own. The only thing keeping any of it out of the repository
is that `work/` itself is ignored (`.gitignore:75`). Move a session, or copy
one of these files, outside `work/`, and nothing stops you from committing a
manuscript by accident. See [Confidentiality](../concepts/confidentiality.md)
for the rest of what protects a manuscript, and what does not.

## See also

- [Command reference](cli.md) — every flag of every command named above.
- [Tutorial: a complete review, offline](../tutorial.md) — builds and walks
  through the session pasted on this page.
