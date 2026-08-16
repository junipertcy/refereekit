# What verification means

This page states exactly what a `PASS` from `refereekit verify` promises —
narrower than you will assume before reading it.

## Quotation-scoped

Every example below runs `refereekit verify` directly against
`work/tutorial`, the session [the tutorial](../tutorial.md) builds by
answering `refereekit review`'s prompts once; build it the same way and you
will see the same verdicts. The same check also runs automatically — inside
`review`'s question-and-answer loop, on every answer it gets back, and again
inside `draft` and `editor`, on every anchor the draft cites that the
session already established — so running it by hand here shows exactly
what those automatic passes check.

A `PASS` on a `quote` or `page` claim — the two are the same check,
`--anchor` a page number either way (`refereekit/verify.py:53`) — means
one specific thing: these exact words, normalised for whitespace and case,
are on that page (`refereekit/verify.py:66-73`). Nothing broader.

When refereekit extracts citations from generated prose — a `review` answer,
or a drafted report — only text the author put inside quotation marks is
even a candidate for this check; a paraphrase is never compared to the page
at all (`refereekit/quotes.py:1-7`). Typing `--text` yourself at the
command line bypasses that extraction step: whatever you pass is checked
directly, quotation marks or not.

```bash
refereekit verify --session work/tutorial --kind quote --anchor 1 --text "a finite set of nodes"
```

```text
PASS: found on page 1
```

The same words, claimed for a page that does not have them, come back
`FAIL`:

```bash
refereekit verify --session work/tutorial --kind quote --anchor 3 --text "words that are not on that page"
```

```text
FAIL: not found on page 3
```

## A bare citation is `FLAG`, not `PASS`

A page named with nothing quoted — "page 2 sets up the model," with no
quotation marks around any of it — is recorded with empty text, and empty
text verifies as `FLAG`, not `PASS` (`refereekit/verify.py:68-71`). This is
the common case, not the exception: referee prose, whether typed by a
person or drafted by a model, mostly paraphrases the manuscript rather
than quoting it, and a paraphrase has no exact words to check against the
page. `FLAG` reports that honestly, as unverified, rather than treating a
paraphrase as a failed citation.

## A `FLAG` carries a guarantee

A `FLAG` still promises something, because of the order `verify` checks
things in. The page number is resolved and confirmed to exist before the
quotation is looked at (`refereekit/verify.py:53-65`); a citation to a
page that is not in the document is a `FAIL`, never a `FLAG`, however
little of it is quoted. That ordering is what makes a `FLAG` claim safe to
act on: unlike a `FAIL`, its page is confirmed real, only its wording is
unchecked — which is why `review`'s question-and-answer loop records a
`FLAG` claim into the session's claim pool alongside every `PASS`, instead
of discarding it (`refereekit/agent/loop.py:108-116`).

```bash
refereekit verify --session work/tutorial --kind quote --anchor 99 --text "a finite set of nodes"
```

```text
FAIL: page 99 does not exist
```

The quoted words are real and correctly transcribed; the page is not. That
is a `FAIL`, not a `FLAG`, because the one thing a `FLAG` on a `quote` or
`page` claim guarantees — that the page exists — cannot be made here at
all.

## Floors

Two floors keep a short string from passing as evidence, and they act at
different points. When refereekit finds quotations inside generated prose,
a quoted span under 12 characters is dropped before it becomes a citation
at all — a phrase that short collides with the page by accident and cannot
carry a claim (`refereekit/quotes.py:12`). Separately, on a `quote` or
`page` claim, `verify` never returns `PASS` for text of fewer than four
words; it verifies as `FLAG` instead (`refereekit/types.py:53`,
`refereekit/verify.py:68`). `equation` and `figure` claims are existence
checks that never inspect `claim.text`, so this floor is specific to
`quote`/`page` — within that scope, though, it is blind to where the text
came from, applying alike to a quotation refereekit extracted and to a
`--text` you type yourself:

```bash
refereekit verify --session work/tutorial --kind page --anchor 2 --text "model"
```

```text
FLAG: page 2 exists; no quotation to verify: 1 words, need 4
```

By now you have seen all three verdicts appear: `refereekit verify` exits 0
for a `PASS`, 1 for a `FAIL`, and 3 for a `FLAG` — the exit codes for every
command are in the [command reference](../reference/cli.md#exit-codes).

## Folding, not fuzzy matching

Before comparing, refereekit folds typography: Unicode NFKC normalisation
turns compatibility forms such as the "fi" ligature into plain letters,
every width of dash collapses to a hyphen, curly quotation marks become
straight ones, and a soft hyphen vanishes — none of these survive a
referee copying or retyping the same words by hand. A word the typesetter
split across a line break is searched both joined and hyphenated, because
nothing in the extracted text says which reading is correct
(`refereekit/textnorm.py`).

This is folding, not fuzzy matching: every rule maps two spellings of the
same characters onto one, and none of them widens what counts as a match.
A hyphen in the middle of a line is left alone, as content, so a quotation
of `58%` never matches a paper's `5-8%` (`refereekit/textnorm.py:70-72`).

When a `quote` or `page` claim fails, and some line on the page is close
enough to be worth showing, the evidence names it — a diagnostic to help
you spot a transcription slip, not a second chance to pass. Below that
threshold nothing is named: the `not found on page 3` example earlier on
this page is exactly that case, because nothing on page 3 resembles the
claimed words closely enough to print. Either way, a nearest line never
changes the verdict away from `FAIL` (`refereekit/verify.py:10-29`).

## Extraction limits

Figures, equations and sections all come from extraction, and each has a
different limit.

Figures are read from caption lines starting "FIG." or "Figure" followed
by a number (`refereekit/ingest.py:28-35`); the tutorial's fixture paper
yields figures 1 through 4.

Equation anchors are less reliable, because extraction finds real labels
and page-margin noise indiscriminately. A `PASS` is confined to what
extraction can actually vouch for: the highest number N such that
1, 2, 3, ... N were all extracted, and any anchor inside that run passes
(`refereekit/verify.py:32-49`). The tutorial's fixture extracts twenty
numeric ids, and the contiguous run starting at 1 stops at 7 — so equation
(18), though it really was extracted, FAILs rather than PASSes:

```bash
refereekit verify --session work/tutorial --kind equation --anchor 18 --text ""
```

```text
FAIL: equation (18) is outside the range extraction can vouch for (1-7)
```

while equation (3), inside the run, PASSes:

```bash
refereekit verify --session work/tutorial --kind equation --anchor 3 --text ""
```

```text
PASS: equation (3) exists
```

This is `FAIL`, not `FLAG`, on purpose (`refereekit/verify.py:88-97`): a
`FLAG` would join the claim pool and stay available to a draft, and an
equation number that extraction cannot vouch for has no business being
citable. One residual case sits outside this rule: a section-numbered
label such as `2.1` is not a plain integer, so the run does not apply to
it — it passes on bare existence in the extracted list instead, kept
deliberately rather than changed silently (`refereekit/verify.py:81-87`).

Figures use no such run — any extracted figure id passes:

```bash
refereekit verify --session work/tutorial --kind figure --anchor 1 --text ""
```

```text
PASS: figure (1) exists
```

Two further limits are worth knowing before you rely on either. Section
detection is best-effort heading-pattern matching, and yields nothing on
many papers — the tutorial's fixture extracts zero sections
(`refereekit/ingest.py:37-44`). And an equation's body is never
reconstructed at all: only its number is extracted, so `verify` can
confirm an equation exists but never what it says
(`refereekit/ingest.py:25`).

## The two draft flags

A different check from the ones above runs whenever `draft` or `editor`
writes a report or letter — and also at the end of `review`'s own
pipeline, which calls those same two functions itself
(`refereekit/agent/loop.py:36,42`); the tutorial's own `(2 flag(s))` count
came from exactly this path. Every anchor the drafted prose cites is
re-extracted and checked against what the session actually established.
This is where two flag reasons come from — `not in verified pool` and
`failed re-verification` (`refereekit/drafts.py:98-112`).

`not in verified pool` means the draft cites a page or equation that the
question-and-answer transcript never established at all: nothing with
that kind and anchor is in the session's claim pool.

`failed re-verification` means the opposite: the anchor was in the pool,
but checking it again, against the session's `doc.json`, now returns
`FAIL`. Two things can cause that. The session's `doc.json` can have been
overwritten by a later `or-fetch` of a revised paper — re-fetching the
same submission number re-ingests it every time
(`refereekit/cli.py:283-284`) — so a claim that verified against the
original submission no longer verifies against the replacement. Or the
drafting model, writing the citation into its own prose, can have altered
the quoted words from what the pool actually recorded — re-verification
checks the words the draft wrote, not the words originally stored, so an
altered quotation is caught here.

## What verification cannot do

Verification cannot tell you whether a mathematical claim is true. Whether
Eq. (25) is actually an identity is not a question about whether some
words are a substring of a page — a `PASS` on an `equation` claim confirms
only that the number falls inside the run extraction can vouch for, never
what the equation says or whether it is correct. Checking a derivation
stays your own work: work it out by hand, or write a script and check it.

## See also

- [Confidentiality](confidentiality.md) — what happens to the manuscript
  text itself, as distinct from what verification checks about a citation
  to it.
- [Command reference](../reference/cli.md) — every flag of `verify`,
  including the kinds, such as `table`, that cannot be checked
  mechanically and always come back `FLAG`.
- [The tools on their own](../guides/piecemeal.md) — running `verify` by
  hand against your own draft, outside `review`'s loop.
