# Tutorial: a complete review, offline

*This needs [part 1 of the install](install.md#part-1-get-it-running) and
nothing else: no API key, no account, and after the install no network.*

This page runs the whole `review` pipeline once, on the paper the repository
ships as a test fixture, so you can watch what refereekit does before you
point it at a manuscript that matters. The paper is
`tests/fixtures/real_paper.pdf`, the author's own published paper, and the
model is replaced by a fake backend that returns one fixed string for every
call it gets. So the summary, every answer, the report and the editor's
letter will all be that same string, and none of them is a judgement of the
paper: nothing here shows you how well a model reviews. What is real is
everything refereekit does *around* the model — ingesting the PDF, checking
every citation in the generated prose against it, building the pool of
claims that verified, and gating both drafts on that pool. That machinery is
the part worth seeing first, because it is the part you will be relying on.

## 1. Set up the fake backend

```bash
export REFEREEKIT_FAKE=1
export REFEREEKIT_FAKE_TEXT='On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".'
```

`REFEREEKIT_FAKE=1` selects the fake backend instead of an SDK, and
`REFEREEKIT_FAKE_TEXT` is the string it returns for every call. Both are in
[Environment variables](reference/environment.md); without the second the
fake backend answers with the single word `draft`, which cites nothing and
would make a dull tutorial.

This string is three sentences, and each one makes a single citation,
because refereekit attributes a quotation to the page cited in the same
sentence. The three are chosen to come back one of each verdict: the
quotation attributed to p. 1 really is on page 1, `Page 2` is a bare pointer
with nothing quoted, and the quotation attributed to p. 3 is not on page 3.
That gives you a PASS, a FLAG and a FAIL out of one answer.

## 2. Run the review

```bash
refereekit review tests/fixtures/real_paper.pdf --session work/tutorial
```

`review` is the whole pipeline in one command, and it asks you questions as
it goes. Here is the run, as a terminal shows it — refereekit's prompts, and
what you type after each one:

```text
SUMMARY:
On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".
question> What does the paper study?
On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".  ⚠ CITATION FAILED: page (3); unquoted, not verified: page (2)
question>
verdict (recommend)> minor revision
venue> PRX
major/minor> minor
section lengths (name=len, comma-sep; blank=default)>
editor-answer key (blank to end)>
review complete: work/tutorial/ours/report.txt, work/tutorial/ours/editor.txt (2 flag(s))
```

**The summary.** `review` ingests the PDF and asks for a summary before it
asks you anything, and prints it under `SUMMARY:`. With a real model this is
the first thing worth reading; here it is the fixed string.

**The question-and-answer loop, and what an anchor is.** Type a question and
refereekit answers it from the manuscript — but it checks the answer before
it shows it to you. What it checks are the answer's *anchors*: the pointers
the prose makes into the PDF, a `p. N` or an `Eq. (N)`. Each anchor is
verified against this document, and the three in this answer come back
differently.

- `"a finite set of nodes"`, attributed to p. 1: those exact words are on
  page 1, so the claim PASSes and joins the session's claim pool.
- `Page 2`, with nothing quoted: unverified, because there are no words to
  check — but page 2 exists, so it is a FLAG rather than a failure, and a
  FLAG joins the pool too. Its page is confirmed real; only its wording is
  unchecked.
- the quotation attributed to p. 3: those words are not on page 3, so it
  FAILs and stays out of the pool.

The line refereekit appends to the answer names the last two:
`⚠ CITATION FAILED: page (3); unquoted, not verified: page (2)`. Exactly
what each verdict promises — and what a PASS does not promise — is
[What verification means](concepts/verification.md).

The loop keeps asking, so ask as many questions as you like. Press Enter on
a blank line to finish asking.

**The verdict gate.** Three prompts, and all three answers are yours rather
than the model's: `verdict (recommend)>` takes your recommendation in your
own words (`minor revision`), `venue>` the venue (`PRX`), `major/minor>` how
serious the revisions are. They are recorded as typed and become an input to
the report draft; the editor's letter is written from the claim pool and
your answers to the editor, and never sees the verdict at all. The venue
typed here is recorded on the verdict, and that is late — `review` has
already decided whether to open a venue memory by then, so pass `--venue` on
the command line if you want one — but a later `draft` or `editor` run on
this session does fall back to it. See [The session
directory](reference/session.md).

**The section-length gate.** `section lengths (name=len, comma-sep;
blank=default)>` is blank above, which accepts the defaults. To make one
section shorter, type `summary=short`, and separate several with commas.

**The editor-answer gate.** Editors' questions usually come lettered, so
this loop asks for a key and then its answer: type `a`, press Enter, type
the answer to (a). A blank key ends the loop, which is what the blank above
does — the letter is drafted with no answers folded into it.

Then the last line: both drafts are written, and `(2 flag(s))` counts the
citations inside them that refereekit could not stand behind. It is only a
count — [section 3](#3-what-landed) gets the two lines that say what they
were.

The same run, without typing, is one line — this is the form to put in a
script:

```bash
printf 'What does the paper study?\n\nminor revision\nPRX\nminor\n\n\n' | refereekit review tests/fixtures/real_paper.pdf --session work/tutorial
```

```text
SUMMARY:
On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".
question> On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".  ⚠ CITATION FAILED: page (3); unquoted, not verified: page (2)
question> verdict (recommend)> venue> major/minor> section lengths (name=len, comma-sep; blank=default)> editor-answer key (blank to end)> review complete: work/tutorial/ours/report.txt, work/tutorial/ours/editor.txt (2 flag(s))
```

The seven lines `printf` writes are the seven answers above, blanks
included. The output looks jammed together only because a prompt is printed
without a trailing newline, and piped input is never echoed back: nothing
moves to a new line until refereekit itself prints one. The two blocks are
the same run in two layouts — same session, same claims, same two flags.

`review` appends to the session it is given, so if you have already run it
once, delete `work/tutorial` before running it again; otherwise the second
run's claims pile on top of the first run's and the state below will not
match.

## 3. What landed

```bash
ls work/tutorial work/tutorial/ours
```

```text
work/tutorial:
doc.json
index.html
ours
state.json

work/tutorial/ours:
editor.txt
report.txt
```

`doc.json` is the ingested manuscript: the text page by page, plus the
figure and equation anchors extraction found — and an empty section list,
because heading detection finds none in this paper. `index.html` is the
question-and-answer page, `state.json` the claim pool and the verdict, and
`ours/` the drafts. A session fetched from OpenReview holds more; every
entry that can appear, and which command writes it, is in [The session
directory](reference/session.md).

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

`qa_count` records the one question asked, and the pool holds two claims out
of the answer's three citations: page 1 with the words that verified, and
page 2 with `text` empty, which is what a bare pointer looks like once
recorded — a `FLAG` is kept, not discarded. Page 3 is not
there at all — a FAIL is reported to you in the transcript and then
discarded, because the pool is what the drafts are allowed to draw on.

```bash
cat work/tutorial/ours/report.txt
```

```text
On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".
```

With a real model this file is your referee report, drafted from the pool
above and in the voice of the style guide. Here it is the fixed string
again, which is the point of the next command: the string cites page 3, and
page 3 is not in the pool.

```bash
refereekit draft --session work/tutorial
```

```text
report: wrote 124 chars, 1 flag(s)
  FLAG page (3): not in verified pool
```

`review` printed a count and nothing more; `draft` re-runs the report on the
same session and prints one line per flag, which is how you find out what
the count was about. `not in verified pool` means the drafted prose cites an
anchor the question-and-answer transcript never established: page 3 failed
verification, so nothing with that kind and anchor is in the pool, and the
draft is flagged for citing it rather than quietly trusted. The editor's
letter cites page 3 too, and is flagged for it in the same way — those two
are the `(2 flag(s))`. `draft` overwrites `ours/report.txt`; the drafts are
always safe to regenerate.

```bash
refereekit serve --session work/tutorial
```

```text
serving work/tutorial at http://127.0.0.1:8888/
```

`serve` offers the session directory as static files on `127.0.0.1`, at port
8888 or the next free one if 8888 is taken, and runs until you interrupt it
with Ctrl-C. It prints whichever port it bound — the line above — and logs
each request beneath it.

Open the URL and you get `index.html`, the question-and-answer page, with
mathematics typeset. That page pulls MathJax from a CDN, which is the only
request that leaves your machine in this whole tutorial, and the browser
makes it, not refereekit, which sends nothing anywhere. The page also polls
the local server every 1.5 seconds, so that it reloads itself once you
answer another question; that is what keeps filling the request log, and it
never leaves the loopback address. Offline the page still loads, and its
mathematics simply stays as raw TeX.

## 4. Verify a quotation by hand

The check that ran inside the loop is also a command of its own, so you can
put a claim to the PDF directly — useful when you are checking a sentence
you wrote yourself. These three reproduce the three verdicts from the
answer.

```bash
refereekit verify --session work/tutorial --kind quote --anchor 1 --text "a finite set of nodes"
```

```text
PASS: found on page 1
```

```bash
refereekit verify --session work/tutorial --kind quote --anchor 3 --text "words that are not on that page"
```

```text
FAIL: not found on page 3
```

```bash
refereekit verify --session work/tutorial --kind page --anchor 2 --text "model"
```

```text
FLAG: page 2 exists; no quotation to verify: 1 words, need 4
```

The last one shows the floor: one word is under the four-word minimum, so it
can never come back PASS, because a string that short turns up on a page by
accident and cannot carry a claim. The `page` and `quote` kinds run the same
check either way.

Each verdict has its own exit status — 0 for PASS, 1 for FAIL, 3 for FLAG,
and the rest are in the [command
reference](reference/cli.md#exit-codes) — so `verify` composes into a script
without parsing its output. Read the status of the command you just ran with
`echo $?` in bash or zsh, or `echo $status` in fish:

```bash
refereekit verify --session work/tutorial --kind quote --anchor 3 --text "words that are not on that page"; echo $?
```

```text
FAIL: not found on page 3
1
```

## Next

- [Install, part 2](install.md#part-2-model-access-and-openreview) — the
  model access a run against a real manuscript needs.
- [Reviewing for a journal](guides/journal-review.md) — the same pipeline
  end to end on a paper you were actually sent.
- [What verification means](concepts/verification.md) — what a PASS
  promises, precisely, and what it does not.
