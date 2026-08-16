# Reviewing on OpenReview

This page follows a submission assigned to you on OpenReview through the
four commands refereekit gives you for one: fetching the paper and the
venue's review form, reading the paper into a verified claim pool, drafting
the form's prose fields from that pool, and reading what came back.

Every block below that talks to OpenReview carries a line saying it was not
run while this page was written. The rest are pasted from real runs that
never touch OpenReview: the input errors, and a complete `or-draft`
demonstration built offline from [the tutorial](../tutorial.md)'s session
and a review form shipped with the tests.

## Setup

The OpenReview client is an optional dependency, so it is not installed
unless you ask for it (`pyproject.toml:13`):

```bash
.venv/bin/pip install -e ".[openreview]"
```

Only `or-fetch` needs it. `or-draft` and `or-responses` work from what
`or-fetch` already downloaded, so they need neither the extra nor the
credentials — see [Install, part 2](../install.md#openreview).

The credentials are `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD`, read
from the process environment and from nowhere else. There is no flag for
either, deliberately: a password passed as a flag lands in your shell
history and is visible in the process table for as long as the command runs
(`refereekit/openreview/client.py:35-37`). Put them in `.env`, which already
lists both, and let your shell export them
([Install](../install.md#your-env) has the loader for each shell). An empty
value is rejected exactly as an absent one is, so a `.env` with the username
filled in and the password left blank fails the same way an untouched one
does, rather than attempting a login (`client.py:45-47`):

```bash
refereekit or-fetch --venue ICLR.cc/2026/Conference --session work/or-demo
```

```text
error: set OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD
```

Exit code 2, no request made, and no `work/or-demo` directory created — the
client is built before anything else happens, so this refusal lands before
the venue is looked up and before the session is touched.

`--venue` takes an OpenReview venue id, not a venue name: the full path
form, `ICLR.cc/2026/Conference`. Get it wrong and listing your assignments
fails with `error: no venue <venue>; check the venue id`, followed by an
example id (`client.py:99-101`). With `--number`, a wrong id does not
produce that message — the fetch fails on the submission instead, with
`error: could not read submission <N> at <venue>: <reason>` or
`error: submission <N> is not assigned to you at <venue>`, the second being
what an unassigned paper and a nonexistent one both look like, because the
venue restricts readership to the assigned committee (`client.py:115-125`).

## Find your assignments

`or-fetch` without `--number` lists the papers assigned to you and returns.
The list is built from the assignment edges pointing from your profile at
the venue, so it is what the venue has you down for rather than what you
remember agreeing to.

*Not run while writing this page: needs an OpenReview account.*

```bash
refereekit or-fetch --venue ICLR.cc/2026/Conference --session work/iclr
```

One line per assignment, the number then the title (`  <number>  <title>`),
then `Fetch one with: --number <N>`. With nothing assigned to you it prints
`no assignments for you at <venue>` and stops there.

Between those two it can print a third line:
`could not read <N> assigned submission(s): <ids>`. An assignment edge names
a submission id but carries neither number nor title, so each one has to be
resolved separately, and one that will not resolve — usually a withdrawn or
desk-rejected paper still carrying its edge — would once have lost the whole
list. It is now skipped and named instead, so a short list is visibly short
rather than quietly wrong (`client.py:82-93`).

`--session` is required by the parser but untouched in this mode: no
directory is created, because listing starts nothing. The session name
matters from the next command on.

## Four commands, and why four

*Not run while writing this page: needs an OpenReview account.*

```bash
refereekit or-fetch --venue ICLR.cc/2026/Conference --number 42 --session work/iclr-42
refereekit review work/iclr-42/paper.pdf --session work/iclr-42 --venue ICLR.cc/2026/Conference
refereekit or-draft --session work/iclr-42 --db work/memory.db
refereekit or-responses --session work/iclr-42
```

The second command is the one that looks redundant and is not. `or-fetch`
downloads the paper and the form; `review` reads the paper with you and
records the verified claims and your verdict; `or-draft` writes the form's
prose fields from that pool. There is no shortcut, because the pool is what
the prose is built from — `or-draft` against a session that has only been
fetched exits 2 and names the `review` command to run, rather than inventing
four fields and reporting success. What that pool is, and what a claim in it
promises, is [What verification means](../concepts/verification.md); the
question-and-answer loop that fills it is the same one [the
tutorial](../tutorial.md) walks through, and everything on [Reviewing for a
journal](journal-review.md) about flags and drafts applies here unchanged.

`--venue` on the `review` line is optional and worth typing anyway.
`or-fetch` recorded the venue in the session, and `review` falls back to
that record when the flag is absent (`refereekit/cli.py:218-219`), so the
venue gate and venue memory both work either way. Typing it makes the run
self-describing in your shell history, and it is the same string on both
lines.

`--session work/iclr-42` is on every line because all four commands work on
one directory, and the whole review lives inside it. What each of them
leaves there is [The session directory](../reference/session.md).

## What a fetch writes and prints

*Not run while writing this page: needs an OpenReview account.*

```bash
refereekit or-fetch --venue ICLR.cc/2026/Conference --number 42 --session work/iclr-42
```

It writes `paper.pdf` and the ingested `doc.json`; records `venue`,
`number`, `forum` and, once a form is found, `invitation_id` in
`state.json`; writes `form.json`; and stores one file per received reply
under `theirs/`. The first line it prints is the paper:
`fetched submission 42: 9 pages`.

The two steps after that are best-effort, and neither failing is an error.
Before the review stage opens there is no invitation to read, so there is no
form:

*Not run while writing this page: needs an OpenReview account.*

```text
no review form at ICLR.cc/2026/Conference/Submission42/-/Official_Review (<reason>); skipping form.json
```

Exit code 0, with `paper.pdf` and `doc.json` on disk — the paper is the part
you need first, and you can start reading it now. The `<reason>` is there
because a 503 or an expired token reported as "the review stage has not
opened" used to send referees to re-run the `or-fetch` they had just run
(`client.py:157-165`). When the form is read instead, the line is
`review form: <X> prose field(s), <Y> to fill in yourself`.

The discussion is best-effort in the same way: `no replies yet; theirs/ left
empty` before the rebuttal period, or `could not read the discussion for
<forum> (<reason>); theirs/ left empty` when the lookup itself failed. When
there are replies, the line counts them, as
`theirs/: 2 new, 0 unchanged, 1 held back`. Each stored reply is named
`<note-id>-<tcdate>.txt` from OpenReview's own creation time, so a rebuttal
the authors revised during the discussion period arrives as a second file
rather than replacing the first, and you can see what changed
(`client.py:271-310`). A later `or-fetch --number 42` into the same session
picks up whatever was missing — the form once the stage opens, the replies
once they exist.

The held-back count is the part to read carefully. `theirs/` means received
from others, and `or-responses` feeds all of it to the model as what came
back; a review of your own stored there would be analysed as agreeing with
itself. Deciding which replies are yours means looking up your own anonymous
reviewer groups for the submission, and that lookup can fail, or come back
empty at a venue that names its reviewer groups in some form refereekit does
not recognise (`client.py:175-191`). When it does, every `Official_Review`
signed by a group rather than by a named profile is held back rather than
guessed at:

*Not run while writing this page: needs an OpenReview account.*

```text
could not confirm these are not your own review, so they were not stored in theirs/:
  <note-id>-<tcdate>.txt
check them by hand on forum <forum>
```

The rest of the discussion still arrives, and the held-back notes are named
so you can open the forum and look. Nothing is lost, and nothing is assumed.

Two things about a fetch that fails. A download that is not a PDF is refused
before `paper.pdf` is created — only the magic bytes distinguish a paper
from an HTML error page, which the PDF reader would otherwise sniff and
ingest as a one-page document, leaving a session that passed for a fetched
one (`refereekit/cli.py:277-280`). But a file that does start with `%PDF`
and is then found malformed is written first and fails during ingestion, so
that one leaves `paper.pdf` behind on exit 2. Read the message rather than
the directory listing: an exit 2 does not promise an empty session, and
re-fetching into it is the right move either way.

## One session, one paper

One session directory holds one submission. Point `--number 43` at a session
that already fetched 42 and `or-fetch` refuses before it writes anything:

*Not run while writing this page: needs an OpenReview account.*

```text
error: session work/iclr-42 holds submission 42, not 43; use a fresh --session
directory for a different paper
```

Overwriting would replace `paper.pdf`, `doc.json` and `form.json`, leave
`theirs/` holding two papers' notes, and leave a stale `ours/openreview.md`
that `or-responses` would read as your review of the new paper. The
write-once rule on `theirs/` cannot catch it, because two papers' filenames
are legitimately distinct (`cli.py:259-270`). Use a fresh `--session` per
submission — `work/iclr-42`, `work/iclr-43` — exactly as [Reviewing for a
journal](journal-review.md) uses one session per manuscript.

Re-fetching the *same* number is allowed, and is how you pick up a rebuttal
or a revised PDF. Know what it does: it re-downloads the paper and re-ingests
it, so `paper.pdf` and `doc.json` become the current version, while the
claims recorded in `state.json` were verified against the earlier one. The
pool is not re-checked at fetch time — it is re-checked when you next draft,
against whatever `doc.json` now holds (`refereekit/drafts.py:98-112`). A
quotation the authors reworded therefore turns from a verified claim into a
`failed re-verification` flag on the next `or-draft`, which is the flag
telling you to look at that sentence against the new PDF. [What verification
means](../concepts/verification.md#the-two-draft-flags) has both flag
reasons in full.

## Drafting the form's prose fields

`or-draft` needs two things in the session: `form.json`, which only
`or-fetch` writes, and a claim pool from a `review` pass. Everything in this
section is reproducible offline, because a demo session can be built from
[the tutorial](../tutorial.md)'s session and a review form taken from a test
fixture rather than from a fetch. Set up the fake backend as [the
tutorial](../tutorial.md#1-set-up-the-fake-backend) does, then:

```bash
rm -rf work/tutorial work/or-demo
printf 'What does the paper study?\n\nminor revision\nPRX\nminor\n\n\n' | refereekit review tests/fixtures/real_paper.pdf --session work/tutorial >/dev/null
mkdir -p work/or-demo && cp work/tutorial/doc.json work/or-demo/
python -c "import json; from refereekit.openreview import form as f; open('work/or-demo/form.json','w').write(f.to_json(f.parse_form(json.load(open('tests/fixtures/openreview_default_form.json')))))"
```

That `python -c` line is not a step you would ever run for a real
submission — it converts a stored invitation into the same `form.json` a
real `or-fetch` would write, so that the rest of this section runs with no
account, against a form nobody submitted anything to. The
fixture is OpenReview's default review form: `title`, `review`, `rating`,
`confidence`.

`or-draft` checks four things before it builds a backend at all, so a typo
is reported as a typo rather than as a problem with your model access. In
order — the venue gate on the venue `or-fetch` recorded, then `form.json`,
then every `--length` name, then the claim pool:

```bash
refereekit or-draft --session work/tutorial
```

```text
error: no form.json; run or-fetch --number first
```

```bash
refereekit or-draft --session work/or-demo
```

```text
error: no verified claims in this session; run refereekit review work/or-demo/paper.pdf --session work/or-demo first
```

```bash
refereekit or-draft --session work/or-demo --length summary
```

```text
error: --length takes name=value, e.g. --length summary=short
```

That third run is the same pool-less session as the second, and it reports
the malformed `--length` rather than the empty pool, which is the check
order above visible from outside.

Copy the tutorial's `state.json` across and the demo session has a pool:

```bash
cp work/tutorial/state.json work/or-demo/
refereekit or-draft --session work/or-demo --length nosuch=short
```

```text
error: --length names no field in this form: nosuch
```

All four exit 2. That last one is worth having: a `--length` naming no field
is either a typo or a form that differs from the one you expected, and both
are worth hearing about before a draft is written
(`refereekit/openreview/fill.py:44-56`).

With a form and a pool, it drafts:

```bash
refereekit or-draft --session work/or-demo
```

```text
openreview: 2 prose field(s) drafted, 1 flag(s)
  FLAG page (3): not in verified pool
to fill in yourself:
  rating                   (1-10)
  confidence               (1-5)
```

Two prose fields drafted, two left blank, and one flag — the fake backend's
fixed answer cites p. 3, which the tutorial's question-and-answer loop never
got into the pool, so the citation is unearned. A flag means here exactly
what it means under `review`; [Reviewing for a
journal](journal-review.md#read-the-flags) has what to do about each of the
two reasons.

`ours/openreview.md` is the file you read and paste into the web form:

```bash
cat work/or-demo/ours/openreview.md
```

```text
# Test.cc/2027/Conference/Submission42/-/Official_Review

## title
<!-- Brief summary of your review. -->

On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".

## review
<!-- Please provide an evaluation of the quality, clarity, originality and significance of this work. -->

On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".

## rating

(fill in yourself. options: 10: 10: Top 5% of accepted papers, seminal paper; 8: 8: Top 50% of accepted papers, clear accept; 5: 5: Marginally below acceptance threshold; 1: 1: Trivial or wrong)

## confidence

(fill in yourself. options: 5: 5: The reviewer is absolutely certain; 3: 3: The reviewer is fairly confident; 1: 1: The reviewer's evaluation is an educated guess)
```

The H1 is the invitation the form came from — here the fixture's own id, in
a real session the one `or-fetch` recorded as `invitation_id`. Then one
`## <field>` per field in the venue's own order, each with the venue's
instruction to the reviewer as an HTML comment, so you can see what you were
asked for while you edit. Under `title` and `review` is the drafted prose —
here the fake backend's fixed string, twice, because both fields were
drafted from the same pool. Under `rating` and `confidence` is
`(fill in yourself. options: …)`. In those option lists the value appears
twice, as `10: 10: Top 5% …`, because this venue's own description of each
choice starts by repeating the number; refereekit prints the value and the
description it was given.

Alongside it, `ours/openreview.json` maps every field name to its value,
with a blank field present as `""` — so the mapping lists the whole form and
a reader can see what is still missing (`fill.py:127-133`).

### What gets drafted, and what never does

Nothing with a fixed set of choices is ever filled in. Verification here is
quotation-scoped substring matching: it can confirm that a quoted phrase is
on a page, and it cannot tell a soundness of 3 from a 4
(`refereekit/openreview/fill.py:1-5`). Those fields come back blank, listed
for you, every time.

The other half of that rule is the one to watch. The form is discovered at
runtime from the venue's own invitation, and a field is classified by
whether the invitation gives it a fixed set of choices, not by its name
(`refereekit/openreview/form.py:36-55`). That is what lets one code path
handle every venue's form — and it also means every free-text field on the
form gets drafted, whatever the venue calls it and whoever it is addressed
to. Run the same session against the ICLR-shaped fixture to see it:

```bash
python -c "import json; from refereekit.openreview import form as f; open('work/or-demo/form.json','w').write(f.to_json(f.parse_form(json.load(open('tests/fixtures/openreview_iclr_form.json')))))"
refereekit or-draft --session work/or-demo
```

```text
openreview: 4 prose field(s) drafted, 1 flag(s)
  FLAG page (3): not in verified pool
to fill in yourself:
  soundness                (1-4)      Assess the soundness of the technical claims.
  presentation             (1-4)
  contribution             (1-4)
  rating                   (3-8)      Overall assessment.
  confidence               (1-5)
  flag_for_ethics_review   (No ethics review nee...) Does this submission need an ethics review?
  code_of_conduct          (I agree)
  supplementary            (file)     Optional attachment.
```

Eight fields left for you, with no venue-specific code anywhere: the
numeric ones show their span, the textual ones their choices, truncated to
keep the column aligned, and `supplementary` shows its raw type because a
file upload has no choices to list. The four drafted fields are `summary`,
`strengths`, `weaknesses` — and `confidential_comment`, the box this form
shows only to the area chairs, in `ours/openreview.md` alongside the rest:

```text
## confidential_comment
<!-- Comments visible to the area chairs only. -->

On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".
```

That is the rule made visible. A confidential comment is free text, so it
was drafted; a textbox asking you to disclose your LLM use, or to record
your own unaided assessment, is free text too, so it would be drafted the
same way. Rewrite those by hand. A disclosure box in particular has to be
your own words about what you actually did — a drafted answer to it is
false in the specific way the box exists to prevent. Which venues require
one, and what they require, is a question to settle before you fetch
anything: [Before you start](../before-you-start.md).

`or-draft` takes two more options, and neither of them checks anything —
both shape what is written. `--length <field>=<value>` is repeatable and
applies to one prose field at a time; each field is drafted by its own
backend call, so a call is told only its own length and only its own
instruction from the venue (`fill.py:80-104`). `--db` mirrors
`review`'s: it defaults to `<session>/memory.db`, so passing
`--db work/memory.db` on both commands is what makes notes for a venue
accumulate across every paper you referee there. Memory is opened only when
the session records a venue, and a fetched session always does
(`cli.py:380-382`). [Your voice](your-voice.md) covers both the style guide
and what a stored note may say.

## Reading what came back

`or-responses` reads everything under `theirs/` as what came back from
others, and `ours/openreview.md` as your own review — falling back to
`ours/report.txt` if you have not drafted the form yet
(`cli.py:428-433`). It writes `ours/response-analysis.txt`.

An empty `theirs/` is an input error, checked before a backend is built so
it cannot first fail on a missing key:

```bash
refereekit or-responses --session work/or-demo
```

```text
error: no received notes in theirs/; nothing to analyze
```

Exit code 2. The demo session above has no `theirs/` at all, because nothing
built it: only `or-fetch` writes there.

What it produces is a reading aid, not a verdict. The prompt asks for three
things — the points you raised that the response addresses, the points it
does not, and the factual claims it makes about the manuscript that you
should re-check — and explicitly forbids recommending a rating, a score, or
a decision, because what a response is worth is your judgement
(`refereekit/openreview/responses.py:1-26`). Author responses quote and
characterise the manuscript, so this command sends manuscript text and is
gated exactly like `or-draft`.

The prompt also requires the analysis to end with one line verbatim
(`responses.py:8-9,25`):

```text
NOTE: claims about a revised manuscript cannot be verified against doc.json, which holds the version originally fetched.
```

That is not a formality. Nothing in a response has been checked against the
paper; `doc.json` holds the version you fetched, and an author writing about
what they changed is describing a document refereekit has never seen. Fetch
the revision if you want those claims checked — see the re-fetch caveat
above, since that is the command that makes `doc.json` current and the pool
stale at the same time.

## Read-only, and the sandbox

refereekit never posts to OpenReview. There is no `post_note_edit` call
anywhere in the package, so posting is not one bug or one wrong flag away —
the code does not exist (`refereekit/openreview/client.py:8-9`). Every
command here reads; the output is written locally for you to read, edit, and
paste into the web form yourself. Submitting a review stays a thing you do
deliberately, in a browser, having read what you are submitting.

`--baseurl` points `or-fetch` at a different OpenReview deployment. It
defaults to `https://api2.openreview.net`; the API sandbox is a way to
exercise the calls without touching production data:

*Not run while writing this page: needs an OpenReview account.*

```bash
refereekit or-fetch --venue ICLR.cc/2026/Conference --session work/iclr --baseurl https://devapi2.openreview.net
```

## Confidentiality

A fetched submission is confidential manuscript text, and everything above
puts more of it on your disk than a journal review does. The rules are the
same ones as everywhere else in refereekit, applied to the files a journal
review never produces.

`paper.pdf` and `doc.json` are the manuscript. Keep the session under
`work/`, which is the one directory `.gitignore` keeps out of the repository
wholesale, and never move a session out of it — see
[Confidentiality](../concepts/confidentiality.md#repository-rules) for what
that line does and does not cover.

`form.json` is the only file here that is not manuscript-derived: it is the
venue's own configuration, parsed from a public invitation, and carries no
paper text at all.

`ours/openreview.md`, `ours/openreview.json` and
`ours/response-analysis.txt` are derived from the manuscript exactly as
`ours/report.txt` is, and are never committed. All three are safe to
regenerate, so nothing is lost by rerunning the command that wrote one.

And the venue's own rule about outside models comes before any of this.
refereekit runs its venue gate on the venue `or-fetch` recorded, so a
fetched session carries that rule with nothing for you to restate — but its
built-in table has exactly one entry and defaults to permitting, so it is a
safety net for a prohibition you already know about, not a source of truth
about your conference. Find out what your venue actually forbids, and what
it requires you to disclose, before you fetch: [Before you
start](../before-you-start.md).

## See also

- [Command reference](../reference/cli.md#or-fetch) — every flag, every
  printed line, and every exit code of the three `or-*` commands.
- [The session directory](../reference/session.md) — what each of the four
  commands leaves in `work/iclr-42`, and the `<note-id>-<tcdate>.txt`
  naming under `theirs/`.
- [Reviewing for a journal](journal-review.md) — the `review` pass in the
  middle of the sequence, in full.
- [Troubleshooting](../troubleshooting.md) — every error on this page, and
  the ones it does not cover.
