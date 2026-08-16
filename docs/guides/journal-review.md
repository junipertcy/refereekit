# Reviewing for a journal

This page follows a single paper through refereekit end to end: what to
check before you run anything, the one command that runs the whole review,
what its flags mean once it finishes, and what to do with the two drafts it
leaves behind. It assumes you have already worked through [the
tutorial](../tutorial.md); the gates are the same ones, so this page does
not repeat their transcript — only what is different once a real model is
answering.

## Before you run

Three things worth having settled before you point `review` at a paper you
were actually sent, so you do not discover they were missing partway
through a real run.

- Check what your venue's own rule on outside models actually says.
  refereekit's built-in table of prohibited venues has exactly one entry,
  so it is a safety net for a rule you already know, not a source of truth
  about your journal. [Before you start](../before-you-start.md) is where
  you record what you found.
- Set up model access for whichever deployment you use — an installed SDK,
  and a key, profile, or project, depending on which.
  [Install, part 2](../install.md#part-2-model-access-and-openreview) walks
  through all three.
- Export `REFEREEKIT_ZERO_RETENTION=1`. Without it, every command that
  could send the manuscript to a model refuses before it does, whichever
  deployment you have configured. Setting it is an attestation about your
  own account, not something refereekit checks for you —
  [Confidentiality](../concepts/confidentiality.md) has the row-by-row
  table of what it asserts on each deployment.

## The PDF and the session

Put the manuscript PDF under `work/` too, next to the session that will
hold everything refereekit does with it — `work/<name>/paper.pdf` is a
natural place, though any path under `work/` works. `work/` is the one
directory `.gitignore` uses to keep a whole tree out of the repository
(`.gitignore:75`), so keeping the PDF there alongside the session means an
absent-minded `git add` cannot commit either one. See
[Confidentiality](../concepts/confidentiality.md) for the rest of what
living under `work/` buys a manuscript, and what it does not.

Give the session its own short name — `--session work/<name>` — and use
one session per paper. A session's claim pool only grows, and nothing
about `review` resets it for a new PDF: point the same session at a second
manuscript and the second paper's claims join the first's in the same
pool, later checked against whichever `doc.json` happens to be on disk at
the time. One paper, one session, keeps that question from ever coming up.

## `--venue` does two things

Passing `--venue` is the most direct way to set it, but not the only one:
`review` resolves the venue in this order — the flag if you gave it,
otherwise a `--spec` file's own `venue`, otherwise a venue this session
already has on record, from an earlier `review` into it or from
`or-fetch` (`refereekit/cli.py:218-219`). However it gets there, that
venue does two separate jobs: it runs the policy gate, and it decides
whether `review` opens a venue memory at all.

The policy gate runs first — before the PDF is opened and before a backend
is even built (`refereekit/cli.py:220-221`) — so a venue refereekit's
table marks as forbidding outside models refuses the whole run
immediately, no matter which deployment you have configured or whether
`REFEREEKIT_ZERO_RETENTION` is set:

```bash
refereekit review tests/fixtures/real_paper.pdf --session work/neurips --venue NeurIPS.cc/2026/Conference
```

```text
review failed: NeurIPS.cc/2026/Conference prohibits sending the submission to an outside model, so this command will not send it. Use the venue's own review interface. If this rule has changed, override it with a REFEREEKIT_VENUE_POLICY file containing:  [venues]
    "NeurIPS.cc/2026/Conference" = { llm = true }
```

Exit code 2, and no `work/neurips` directory is left behind — the refusal
happens before `review` creates one. refereekit's built-in table has
exactly one entry (`refereekit/policy.py:32-34`); every venue it does not
recognise defaults to permitted, because code cannot know your journal's
policy — the table exists to make a prohibition you already know about
impossible to forget, not to discover one for you. The same gate runs in
`draft`, `editor`, `or-draft`, and `or-responses` too; see
[Confidentiality](../concepts/confidentiality.md#the-venue-gate) for all
five.

The second job is quieter. `review` opens a memory database only when
that same resolved venue is known by the time it gets there
(`refereekit/cli.py:225`) — with none of the three above (no `--venue`, no
`--spec`, and nothing already on record), no `memory.db` is created and
there is nothing to recall, even if you type a venue at the verdict
prompt: that answer is saved too late to change this run's decision. The
database it opens defaults to `<session>/memory.db`
(`refereekit/cli.py:222`), one file per session, so a note stored under
one paper's session stays invisible to the next paper's. Pass `--db
work/memory.db` — the same path every time — if you want notes for a venue
to build up across every paper you referee there; see [Your
voice](your-voice.md) for what to do with them once they do.

## The run

*Not run while writing this page: needs an API key.*

```bash
refereekit review work/<name>/paper.pdf --session work/<name> --venue PRX --db work/memory.db
```

Everything from here runs the same steps [the tutorial](../tutorial.md)
walks through against the fixture, in the same order: a summary, printed
before you are asked anything; a question-and-answer loop that checks
every answer's citations as they come back; the verdict gate, which
records your recommendation and the venue; the section-length gate, for
the drafts' length; and the editor-answer gate, for the letter. Nothing
about the gates changes for a real paper. What changes is that a real
question is a considered one: with a real model behind it, what you type
at each `question>` prompt gets a real, citation-checked answer instead of
the tutorial's fixed string, so it is worth pausing over what you ask
rather than typing the first thing that comes to mind. If you would rather
answer every gate from a file than type at each prompt, see [Driving a
review from a spec](review-spec.md).

This same command can also refuse in three more ways, and it is worth
knowing which of them land before anything is sent and which do not. None
of the three needs a key, an account, or a network connection to
reproduce — try each one now, against [the tutorial](../tutorial.md)'s
own session, before you ever run this for real.

Unset `REFEREEKIT_FAKE` first, though, if the tutorial exported it: the fake
backend is marked zero-retention and never builds an SDK client, so with it
still set the first two commands below draft successfully instead of
refusing.

```bash
unset REFEREEKIT_FAKE      # bash, zsh
set -e REFEREEKIT_FAKE     # fish
```

The retention refusal also needs the `llm` extra installed, because
building the SDK client comes first: without the SDK the same command stops
earlier, on `error: cannot use deployment 'anthropic': No module named
'anthropic'`.

If `REFEREEKIT_ZERO_RETENTION` was never exported, the manuscript path
refuses regardless of which deployment or account you have configured —
this one always lands before anything is sent, under `review`, `draft`,
or `editor` alike, because `complete()` checks it before calling the
backend at all (`refereekit/llm.py:29-36`):

```bash
refereekit draft --session work/tutorial
```

```text
error: refusing to send: backend is not marked zero_retention
```

If `REFEREEKIT_BACKEND` names something other than `anthropic`,
`bedrock`, or `vertex` — a typo, usually — refereekit refuses the same
way, before anything is sent, rather than quietly falling back to a
default: a misspelling must not send a manuscript to whichever deployment
happens to be the default:

```bash
REFEREEKIT_BACKEND=foo refereekit draft --session work/tutorial
```

```text
error: unknown deployment 'foo'; expected one of anthropic, bedrock, vertex
```

And if the style guide cannot be found — a typo'd `--style` or
`REFEREEKIT_STYLE` path, or a non-editable install with no
`style/STYLE.md` to fall back to (see [Install, part
1](../install.md#part-1-get-it-running)) — where this lands is not the
same for every command. Under `draft` or `editor` it is exactly like the
two refusals above, caught before anything is sent:

```bash
REFEREEKIT_STYLE=/nonexistent/STYLE.md refereekit draft --session work/tutorial
```

```text
error: Style guide not found: /nonexistent/STYLE.md
```

Under `review` it is not. The style guide is only read once `review`
starts drafting the report — after the summary and every question in the
Q&A loop have already been sent, and after you have answered the verdict
and section-length prompts (`refereekit/agent/loop.py:20-47`;
`load_style` runs inside `drafts.report`/`drafts.editor_letter`,
`refereekit/drafts.py:121,159`). A bad style path does not stop `review`
from sending the manuscript — it only means the report and editor's
letter are never written, with the session's `doc.json`, `state.json`,
and `index.html` already on disk from the steps that came before it.
Check `--style` and `REFEREEKIT_STYLE` before a live `review` run rather
than counting on this to catch a typo early; if it does happen anyway,
fix the path and re-run `draft` or `editor` on the same session rather
than the whole review.

All three exit 2, wherever they land.

## Read the flags

`review complete: <report path>, <editor path> (<N> flag(s))` is only a
count — it tells you the drafts contain a citation the checker could not
stand behind, not which one. To find out, run `refereekit draft --session
work/<name>`: it redrafts `ours/report.txt` from the same claim pool and
prints one `FLAG <kind> (<anchor>): <reason>` line per flag, instead of
just the total. Against the tutorial's own session, with [the
tutorial](../tutorial.md#1-set-up-the-fake-backend)'s `REFEREEKIT_FAKE`
exported again if you unset it for the refusals above:

```bash
refereekit draft --session work/tutorial
```

```text
report: wrote 124 chars, 1 flag(s)
  FLAG page (3): not in verified pool
```

(This session's `review complete` line reported `(2 flag(s))`, not `1` —
`draft` only redrafts and re-checks the report, and the difference is the
editor's letter's own flag. See [the
tutorial](../tutorial.md#3-what-landed) for both.)

There are exactly two reasons a flag can give
(`refereekit/drafts.py:98-112`), and each tells you something different
about the sentence.

`not in verified pool` means the drafted sentence cites a page or equation
that your question-and-answer transcript never established — nothing with
that kind and anchor made it into the session's claim pool, so the
citation is unearned. Ask about it directly and let it earn its place in
the pool, or cut the sentence.

`failed re-verification` means the anchor was in the pool once, but
checking it again against the session's current `doc.json` now comes back
FAIL — either the session was re-ingested from a revised paper since, or
the drafting model altered the quoted words when it wrote the citation
into its own prose. Check the sentence by hand against the PDF; see [What
verification means](../concepts/verification.md#the-two-draft-flags) for
both causes in full.

A draft with an empty pool and no flags at all is a draft that cited
nothing — the only way zero citations can produce zero flags with nothing
in the pool to draw on.

## Edit the drafts

`ours/report.txt` and `ours/editor.txt` are starting points, not finished
text — edit them by hand like any other draft; `ours/` is always safe to
regenerate, so nothing is lost by rerunning the command that wrote a file.
Instead of hand-editing, you can also ask for one part again: `--length
summary=short` (repeatable) on `draft` shortens one section of the
report, and `--answers a=<answer>` (repeatable) on `editor` answers one of
the editor's lettered questions. Both are on [the command
reference](../reference/cli.md). If the drafted voice itself is wrong —
too hedged, too terse, citing in the wrong format — that is the style
guide's job to fix, not a flag: see [Your voice](your-voice.md).

## Afterwards

Once both drafts are as you want them, it is worth storing a short note in
your own words about how you weighed this paper for this venue — what
"minor" meant here, what you tend to flag, anything that would help the
next paper for the same venue go faster. Use the same `--db
work/memory.db` path from earlier, so the note accumulates across every
paper rather than living inside just this one session:

```bash
refereekit mem-store --session work/tutorial --venue PRX --kind verdict --text "PRX: lean accept-after-major on approximate-but-validated theory" --db work/memory.db
```

```text
stored note for PRX
```

That note is recalled automatically the next time you run `review` with
`--venue PRX --db work/memory.db` against a new paper for the same venue —
`review` is what wires memory through to the drafts; rerunning `draft` or
`editor` on the same session does not consult it. `mem-store` guards what
goes in, too: a note that turns out to be a fragment of the manuscript
rather than your own judgement is refused, not stored. See [Your
voice](your-voice.md) for what the guard rejects and how to phrase a note
that will pass it.

## See also

- [Driving a review from a spec](review-spec.md) — answer every gate from
  a file instead of typing at each prompt.
- [Your voice: the style guide and venue memory](your-voice.md) — shaping
  the drafted voice, and what a stored note can and cannot say.
- [The tools on their own](piecemeal.md) — running `ingest`, `verify`, or
  `draft` by hand, outside `review`'s loop.
- [Troubleshooting](../troubleshooting.md) — every error message on this
  page, and the ones it does not cover.
