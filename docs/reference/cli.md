# Command reference

This page is the complete reference for every `refereekit` subcommand — its
flags, defaults, what it writes and prints, and its exit codes; the guides,
starting with [the tools on their own](../guides/piecemeal.md), say when you
would reach for which one.

## Conventions

- `--session` always names a directory under `work/`. Three commands create
  it if it does not already exist — `ingest`, `review`, and `or-fetch` (when
  given `--number`) — because each is a way to start a session. Every other
  command requires the directory, and usually `doc.json` inside it, to
  already exist.
- Errors go to stderr, not stdout, so a report you redirect to a file never
  picks one up by accident. See **Exit codes**, below, for the prefixes.
- Every command below is shown as you would type it, with the virtual
  environment active — see [Install](../install.md#part-1-get-it-running) if
  `refereekit` is not yet on your path.

## `ingest`

```bash
refereekit ingest <pdf> --session work/<name>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `pdf` (positional) | yes | — | Path to the manuscript PDF. |
| `--session` | yes | — | Session directory to create. |

Creates the session directory first, then reads the PDF — so a failed
`ingest` still leaves an empty session directory behind, ready for a second
attempt with the right path.

**Writes:** the session directory, then `doc.json` inside it (the extracted
pages, equations and figures).

**Prints:** `ingested: <N> pages, <M> equations` on success.

```bash
refereekit ingest tests/fixtures/real_paper.pdf --session work/ref
```

```text
ingested: 9 pages, 20 equations
```

On a PDF that does not exist:

```bash
refereekit ingest work/nonexistent.pdf --session work/ref2
```

```text
error: no such file: 'work/nonexistent.pdf'
```

**Exit:** 0 on success; 2 if the PDF cannot be found or read.

## `verify`

```bash
refereekit verify --session work/<name> --kind <kind> --anchor <anchor> --text <text>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--session` | yes | — | Session with `doc.json` already ingested. |
| `--kind` | yes | — | `quote`, `page`, `equation`, `figure`, or any other string. |
| `--anchor` | yes | — | Page number (`quote`/`page`); equation or figure id, e.g. `18` or `2.1` (`equation`/`figure`). |
| `--text` | yes | — | The quoted text to check. Required for every `--kind`, but only checked for `quote`/`page` — pass an empty string for the others. |

`quote` and `page` are the same check: `--anchor` is a page number, and
`--text` must appear on that page, typography folded (see
[What verification means](../concepts/verification.md)). `equation` and
`figure` check only that the anchor id was extracted from the document at
all. Any other `--kind` cannot be checked mechanically, so it always comes
back as a FLAG. `verify` checks one claim and prints the verdict; it does
not add anything to the session's claim pool — only `review`'s interactive
loop does that.

**Writes:** nothing.

**Prints:** `<STATUS>: <evidence>`, one line.

```bash
refereekit verify --session work/ref --kind quote --anchor 1 --text "a finite set of nodes"
```

```text
PASS: found on page 1
```

```bash
refereekit verify --session work/ref --kind equation --anchor 18 --text ""
```

```text
FAIL: equation (18) is outside the range extraction can vouch for (1-7)
```

```bash
refereekit verify --session work/ref --kind table --anchor 1 --text "whatever it says"
```

```text
FLAG: 'table' claim needs human confirmation
```

**Exit:** 0 for PASS, 1 for FAIL, 3 for FLAG. A session with no `doc.json`
exits 2, with Python's own message for a missing file:
`error: [Errno 2] No such file or directory: 'work/<name>/doc.json'`.

## `serve`

```bash
refereekit serve --session work/<name> --port 8888
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--session` | yes | — | Session directory to serve. |
| `--port` | no | `8888` | TCP port on `127.0.0.1`. |

Serves the session directory as static files on `127.0.0.1` and runs until
you interrupt it. It never exits 2: a session that does not exist, or one
with no `index.html`, serves 404s rather than refusing to start —
`index.html` is written only by `review`. If the port is already taken,
`serve` tries the next one, up to 50 times, and prints whichever port it
actually bound.

**Writes:** nothing.

**Prints:** `serving <dir> at http://127.0.0.1:<port>/`, once, before it
starts serving.

**Exit:** 0, once interrupted; `serve` does not return on its own otherwise.

## `draft`

```bash
refereekit draft --session work/<name> --length <name>=<value> --style <path>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--session` | yes | — | Session with `doc.json`; `state.json` (the verified claim pool and verdict) is optional. |
| `--length` (repeatable) | no | — | `name=value`, overrides one section's length, e.g. `--length intro=short`. |
| `--style` | no | see below | Path to a style guide file. |

Reads the venue this session already has recorded — from an earlier
`review` or `or-fetch` — and refuses before building a backend if that
venue forbids outside models. Style is resolved in this order: the
`--style` flag, then the `REFEREEKIT_STYLE` environment variable, then the
checkout's own `style/STYLE.md` (see
[Environment variables](environment.md)). If `state.json` is missing or has
no verified claims, `draft` still runs, from an empty pool, and flags the
report rather than refusing.

**Writes:** `ours/report.txt`.

**Prints:** `report: wrote <N> chars, <K> flag(s)`, then one
`  FLAG <kind> (<anchor>): <reason>` line per flag — for example
`report: wrote 124 chars, 1 flag(s)` followed by
`  FLAG page (3): not in verified pool`.

**Exit:** 0 on success; 2 on a missing session, a `--length` value with no
`=` (printed as the raw
`error: dictionary update sequence element #0 has length 1; 2 is
required`, which means a missing `=`, not a fault in refereekit), a venue
refusal, a zero-retention refusal, or a missing style file.

## `editor`

```bash
refereekit editor --session work/<name> --answers <key>=<value> --style <path>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--session` | yes | — | Session with `doc.json`; `state.json` is optional. |
| `--answers` (repeatable) | no | — | `key=value`, an answer to one of the editor's questions. |
| `--style` | no | see `draft` | Path to a style guide file; same resolution order as `draft`. |

Same venue gate and style resolution as `draft`. An `--answers` value with
no `=` fails the same way `--length` does on `draft`.

**Writes:** `ours/editor.txt`.

**Prints:** `editor: wrote <N> chars, <K> flag(s)`, then one
`  FLAG <kind> (<anchor>): <reason>` line per flag.

**Exit:** 0 on success; 2 on a missing session, a malformed `--answers`
value, a venue refusal, a zero-retention refusal, or a missing style file.

## `mem-store`

```bash
refereekit mem-store --session work/<name> --venue <venue> --kind <kind> --text <text> --db <path>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--session` | yes | — | Session with `doc.json`, used only to guard `--text` against the manuscript. |
| `--venue` | yes | — | Venue the note is filed under. |
| `--kind` | yes | — | Free-form label, e.g. `verdict`, `style`. |
| `--text` | yes | — | The referee-authored note. |
| `--db` | no | `<session>/memory.db` | SQLite database to write to. |

The note text is checked against the session's `doc.json` before it is
stored; a match with the manuscript is refused, not written. Memory is for
what you concluded, never for what the paper says.

**Writes:** one row in the SQLite database at `--db`.

**Prints:** `stored note for <venue>` on success.

**Exit:** 0 on success; 2 on a missing session or a manuscript-text match,
printed as `mem-store failed: <reason>`.

## `mem-recall`

```bash
refereekit mem-recall --venue <venue> --db <path> --limit 20
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--venue` | yes | — | Venue to recall notes for. |
| `--db` | yes | — | SQLite database to read. Unlike `mem-store`, there is no session default — you must name it. |
| `--limit` | no | `20` | Maximum notes to return. |

Prints the most recent notes for the venue, newest first, deduplicated by
exact text. A `--db` path that does not exist yet is created, empty, as a
side effect of opening it, and the command prints nothing and exits 0 — so
a typo in the path is silent, not an error.

**Writes:** nothing to the notes table; see the empty-database note above.

**Prints:** one `[<venue>/<kind>] <text>` line per note, most recent first.

**Exit:** 0 on success, including zero notes; 2 on a database error,
printed as `mem-recall failed: <reason>`.

## `review`

```bash
refereekit review <pdf> --session work/<name> --venue <venue> --spec <path> --db <path> --style <path>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `pdf` (positional) | yes | — | Path to the manuscript PDF. |
| `--session` | yes | — | Session directory to create. |
| `--venue` | no | — | Venue id; see the fallback order below. |
| `--spec` | no | — | TOML review spec that answers every prompt with no typed input; see [Driving a review from a spec](../guides/review-spec.md). |
| `--db` | no | `<session>/memory.db` | Memory database, opened only when a venue is known. |
| `--style` | no | see `draft` | Path to a style guide file; same resolution order as `draft`. |

This is the whole pipeline in one command: ingest, summarise, an
interactive question loop (or a scripted one, under `--spec`), the verdict
gate, and both drafts. The venue is resolved in this order: `--venue`, then
the spec's own `venue`, then whatever venue the session already has
recorded from an earlier `or-fetch` into the same directory. The venue gate
runs on that result before the PDF is opened and before a backend is
built, so a venue that forbids outside models refuses the run before
anything is sent anywhere. `--spec`, when given, is parsed before the gate
and before the PDF, so a spec that cannot drive the run fails before
anything else happens.

**Writes:** `ours/report.txt`, `ours/editor.txt`, `index.html`, and, when a
venue is known, rows in the memory database at `--db`.

**Prints:** a `SUMMARY:` block, the question-and-answer transcript, the
verdict and detail prompts, and finally one line —
`review complete: <report path>, <editor path> (<N> flag(s))` — a count
only; run `draft` on the session afterwards to see the individual flag
lines. See [Tutorial: a complete review, offline](../tutorial.md) for a
worked run with real output.

**Exit:** 0 on success; 2 on a missing or unreadable PDF, a spec error, an
unregistered deployment, a zero-retention refusal, a venue refusal, a note
that repeats the manuscript, or EOF on stdin — printed as
`review failed: <reason>`.

## `or-fetch`

*Not run while writing this page: needs an OpenReview account.*

```bash
refereekit or-fetch --venue <venue> --session work/<name> --number <N> --baseurl <url>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--venue` | yes | — | OpenReview venue id, e.g. `ICLR.cc/2027/Conference`. |
| `--session` | yes | — | Session directory; created only when `--number` is given. |
| `--number` | no | — (omit to list assignments) | Submission number to fetch. |
| `--baseurl` | no | `https://api2.openreview.net` | OpenReview API host. |

Without `--number`, lists the papers assigned to you at the venue and
returns — `--session` is not touched. With `--number`, it first refuses a
session that already recorded a different submission number (use a fresh
`--session` per paper; re-fetching the same number is how you pick up a new
rebuttal), then writes the paper and records `venue`, `number` and `forum`
in `state.json`. Fetching the review form and the discussion is
best-effort: a review stage that has not opened, or a forum with no
replies yet, is not an error — `or-fetch` says so on stdout and exits 0.

**Writes:** `paper.pdf`, `doc.json`; `venue`, `number`, `forum` (and
`invitation_id` when a form was found) in `state.json`; `form.json` when
the review form could be read; one file per confirmed reply under
`theirs/`.

**Prints**, without `--number`: `  <number>  <title>` per assignment, or
`no assignments for you at <venue>`; `could not read <N> assigned
submission(s): <ids>` for any that failed to resolve; `Fetch one with:
--number <N>` when there is at least one.

**Prints**, with `--number`: `fetched submission <N>: <P> pages`; then
either `review form: <X> prose field(s), <Y> to fill in yourself` or
`no review form at <venue>/Submission<N>/-/Official_Review (<reason>);
skipping form.json`; then one of `theirs/: <A> new, <B> unchanged` (with
`, <C> held back` appended when any were), `no replies yet; theirs/ left
empty`, or `could not read the discussion for <forum> (<reason>); theirs/
left empty`. For any reply that could not be confirmed as someone else's:
a line explaining why, one `  <name>` line per held-back note, and
`check them by hand on forum <forum>`.

**Exit:** 0 in every case above; 2 on `error: <reason>` — a bad venue id, a
submission not assigned to you, a download that is not a PDF, or a session
already holding a different paper.

## `or-draft`

*Not run while writing this page: needs an OpenReview account and a
session already fetched with `or-fetch --number`.*

```bash
refereekit or-draft --session work/<name> --length <name>=<value> --style <path> --db <path>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--session` | yes | — | Session fetched with `or-fetch --number`, then reviewed with `review`. |
| `--length` (repeatable) | no | — | `name=value`, overrides one prose field's length. |
| `--style` | no | see `draft` | Path to a style guide file; same resolution order as `draft`. |
| `--db` | no | `<session>/memory.db` | Memory database — same default `review` uses, so the two share a store. |

Checks, in order, before any backend is built: the venue gate, reading the
venue `or-fetch` recorded; that `form.json` exists; that every `--length`
name matches a field on that form; and that the session has a verified
claim pool from a prior `review` run. Only the venue's prose fields are
drafted — every field with a fixed set of choices, such as a rating or a
confidence score, is left blank and listed under "to fill in yourself",
because verification is quotation-scoped and cannot judge a score.

**Writes:** `ours/openreview.md`, `ours/openreview.json`.

**Prints:** `openreview: <N> prose field(s) drafted, <K> flag(s)`, one
`  FLAG <kind> (<anchor>): <reason>` line per flag, then `to fill in
yourself:` followed by one line per blank field —
`  <name>  (<span>)  <description>`, where `<span>` is a numeric field's
min–max range, an enum's choices joined by `|` (truncated if long), or the
field's raw type when it has no enum.

**Exit:** 0 on success; 2 on `error: no form.json; run or-fetch --number
first`, `error: --length takes name=value, e.g. --length summary=short`,
`error: --length names no field in this form: <names>`,
`error: no verified claims in this session; run refereekit review
<session>/paper.pdf --session <session> first`, a venue refusal, or a
zero-retention refusal.

## `or-responses`

*Not run while writing this page: needs an OpenReview account and a
session with replies under `theirs/`.*

```bash
refereekit or-responses --session work/<name>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--session` | yes | — | Session with received replies under `theirs/`. |

Runs the venue gate first, on whatever venue the session has recorded.
Reads every file under `theirs/` as an author or co-referee reply, and
reads `ours/openreview.md` as your own review if it exists, else
`ours/report.txt`. Author responses quote and characterise the manuscript,
so this command sends manuscript text to the backend and is gated exactly
like `or-draft`.

**Writes:** `ours/response-analysis.txt`.

**Prints:** `wrote <path> (<N> received note(s))`.

**Exit:** 0 on success; 2 on `error: no session at <dir>; run or-fetch
--number first`, `error: no received notes in theirs/; nothing to
analyze`, a venue refusal, or a zero-retention refusal.

## Exit codes

| Exit | Meaning |
|---|---|
| 0 | Success. `verify` also uses 0 for a PASS verdict. |
| 1 | `verify` only: FAIL. |
| 2 | An input error; the reason is on stderr. |
| 3 | `verify` only: FLAG. |

`verify` is the only command with three meaningful exit codes; every other
command uses 0 for success and 2 for an input error, with the reason on
stderr behind one of four prefixes: `error:` (most commands),
`review failed:`, `mem-store failed:`, or `mem-recall failed:`. `serve` is
the exception — it does not exit on its own, short of an unhandled
exception, because it runs until you interrupt it. Argparse's own errors,
such as a required flag left off or an unknown subcommand, also exit 2,
with a usage line rather than one of the prefixes above.

## See also

- [The tools on their own](../guides/piecemeal.md) — running each command
  by hand, instead of `review`.
- [Environment variables](environment.md)
- [The session directory](session.md)
- [Troubleshooting](../troubleshooting.md)
