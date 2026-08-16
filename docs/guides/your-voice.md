# Your voice: the style guide and venue memory

Two things shape what a drafted report or letter sounds like: the style
guide pasted into every drafting prompt, and the venue memory notes you
store yourself and refereekit recalls the next time you referee for that
venue.

## The style guide

`style/STYLE.md` in the checkout is the default voice guide. The four
commands that draft prose — `draft`, `editor`, `review`, and `or-draft` —
all choose which file to use in the same order: the `--style` flag, if you
gave one; otherwise the `REFEREEKIT_STYLE` environment variable; otherwise
the checkout's own `style/STYLE.md`, resolved relative to the installed
package (`refereekit/cli.py:162,178,228,359`, default path built at
`refereekit/cli.py:17`). See [Environment
variables](../reference/environment.md) for the same precedence spelled
out for every variable, and [Install, part
1](../install.md#part-1-get-it-running) for why an editable install
matters to that default.

Whichever file wins, its whole text is pasted into the drafting prompt
under a `=== VOICE GUIDE ===` heading (`refereekit/drafts.py:80-83`) — the
model sees it exactly as the file reads, on every call to any of the four
commands above.

Because the file travels with the repository and is meant to be
committed, what belongs in it is not the same as what belongs in a
report. Put in your style guide: how you like a report structured, the
words you reach for at each verdict, and habits of phrasing you want a
draft to imitate. Never put in it a fragment of a report you actually
sent, a manuscript's title, authors, or other identifying details, or
another paper's content — the file sits in git history once committed,
and unlike a session under `work/`, nothing keeps it private.

The shipped `style/STYLE.md` is worth reading as an example of the kind of
thing that belongs in one — voice and structure rules only, with no report
text or manuscript detail anywhere in it — rather than something to copy
outright. A style guide only helps if it is actually yours.

## Venue memory, precisely

`mem-store` writes a note; `mem-recall` reads notes back for a venue.
`review` and `or-draft` are the two commands that consult memory on their
own, when a venue is known; `draft` and `editor` never do.

Store a note once you have settled on a verdict, in your own words:

```bash
refereekit mem-store --session work/tutorial --venue PRX --kind verdict --text "PRX: lean accept-after-major on approximate-but-validated theory" --db work/memory.db
```

```text
stored note for PRX
```

`--session` is required — not because the note is filed under the
session, but because `mem-store` checks `--text` against that session's
manuscript before it writes anything (see *What the guard rejects*,
below). `--venue` files the note; `--kind` is a free-form label
(`verdict`, `style`, whatever you find useful) that comes back in
`mem-recall`'s output but is not otherwise interpreted. `--db` defaults to
`<session>/memory.db` if you leave it off.

Recall every note filed for a venue with `mem-recall`, which requires
`--db` explicitly — unlike `mem-store`, there is no per-session default to
fall back to:

```bash
refereekit mem-recall --venue PRX --db work/memory.db
```

```text
[PRX/verdict] PRX: lean accept-after-major on approximate-but-validated theory
```

Notes come back deduplicated by exact text, newest first, capped at
`--limit` (default 20) (`refereekit/memory.py:37-44`). A `--db` path that
does not exist yet is not an error: opening a `SQLiteMemoryStore` creates
the file and its empty table as a side effect of connecting to it
(`refereekit/memory.py:20-26`), so `mem-recall` against a mistyped path
prints nothing and exits 0 — a silent typo, not a refusal.

`review` and `or-draft` both default `--db` to `<session>/memory.db`, the
same per-session default `mem-store` uses, but only open a store at all
once a venue is already known for that session by the time they get there
(`refereekit/cli.py:222-225` for `review`, `refereekit/cli.py:380-382` for
`or-draft`). With no venue known, neither command opens a store, and
nothing is recalled or written. `draft` and `editor` never take a `--db`
flag and never pass memory into a prompt, however venue-recorded the
session is — redrafting a report or a letter never touches `memory.db`.

Because the default is per session, memory does not carry across papers
unless you make it: a note stored while working `work/alice-paper` is
invisible to `review --session work/bob-paper --venue PRX`, because each
resolves its own `<session>/memory.db` — two different files, even for
the same venue. Pass the same explicit path — `--db work/memory.db` — to
every `mem-store`, `review`, and `or-draft` call for a venue, as this
page's examples do, and every one of them reads and writes the one shared
file instead of its own session's copy. [Reviewing for a
journal](journal-review.md) shows the same recommendation as part of a
full run.

When a store is open, `review` and `or-draft` fold every recalled note's
text into the drafting prompt as `PRIOR NOTES` — the model sees your past
verdicts and habits for that venue as one more input alongside the
verified pool and the style guide (`refereekit/drafts.py:66-71`).

## What the guard rejects

`mem-store` checks `--text` against the session's manuscript before it
writes a row — the same guard that keeps `mem-recall`'s output clean
indirectly, since nothing that fails this check ever reaches the
database. Try storing a note that is not really a note at all — a
quotation from the manuscript itself:

```bash
refereekit mem-store --session work/tutorial --venue PRX --kind quote --text "a finite set of nodes" --db work/memory.db
```

```text
mem-store failed: input is a verbatim manuscript fragment (short verbatim manuscript fragment)
```

Exit code 2, and no row is written. `"a finite set of nodes"` is five
words, and those five words are on page 1 of the fixture paper, so
`--text` is refused before `SQLiteMemoryStore.store` inserts anything
(`refereekit/guard.py:29-75`). (If `--db` had pointed at a path that had
never existed before, the failed call would still leave behind an empty
database file and table — opening a `SQLiteMemoryStore` creates both,
before `.store`'s own check has a chance to refuse anything;
`refereekit/memory.py:20-26`.)

The guard runs two checks, in order, both after folding typography and
case the same way `verify` does — curly quotes, dash variants, and a word
split across a line count as the same text either way
(`refereekit/textnorm.py`). Text under eight words is refused if it
matches a page's wording exactly — the case just shown. Text of eight
words or more is refused the same way if any contiguous eight-word run
inside it appears on a page verbatim, or, short of a single run like
that, if it shares more than one eight-word window with the manuscript
scattered across it (`refereekit/guard.py:29-75`). Against a session
whose document has no extractable text at all, every note is refused
outright, before either check runs, as `cannot verify against an empty
document` (`refereekit/guard.py:52-54`) — there is nothing to compare the
note against, and an unreadable document is a reason to refuse, not a
reason to skip the check.

None of this reads a note for meaning — it is a mechanical comparison
against the manuscript's own wording, so it cannot tell a paraphrase from
a judgement, and it cannot stop you from summarising the paper's argument
in your own sentences. Write what you concluded and why: a verdict, what
"minor" meant for this venue, a phrasing habit worth reusing. Anything
that would let someone reconstruct a sentence of the paper from the note
is the wrong kind of note for memory, guard or no guard.

## See also

- [Reviewing for a journal](journal-review.md) — the same `--db
  work/memory.db` recommendation, and how `--venue` gets recorded for a
  session in the first place, as part of a full review.
- [Command reference](../reference/cli.md) — every flag on `mem-store`
  and `mem-recall`, with their exit codes.
- [Confidentiality](../concepts/confidentiality.md) — the same leak guard
  covers `mem-store`, alongside the venue gate and the zero-retention
  attestation.
