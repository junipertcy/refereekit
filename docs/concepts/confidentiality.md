# Confidentiality

This page states exactly what refereekit sends over a network, what stops
it from sending more, and what protects a manuscript once a session holds
it.

## The one gate

Every prompt refereekit sends to a model passes through one function:
`complete()`, in `refereekit/llm.py:29-36`. Before it calls the backend it
checks one thing — the backend's `zero_retention` attribute — and refuses
unless that attribute is exactly `True`. Reproduce it with `REFEREEKIT_FAKE`
unset: the fake backend is marked zero-retention and never builds an SDK
client, so with it still exported from [the tutorial](../tutorial.md) the
command below drafts instead of refusing.

```bash
unset REFEREEKIT_FAKE      # bash, zsh
set -e REFEREEKIT_FAKE     # fish
```

```bash
refereekit draft --session work/tutorial
```

```text
error: refusing to send: backend is not marked zero_retention
```

Exit code 2. `work/tutorial` has a verdict, but `REFEREEKIT_ZERO_RETENTION`
was never set, so `_backend()` builds a real backend with
`zero_retention=False` (`cli.py:19-36`), and `complete()` refuses before it
ever calls that backend — no request reaches the network, regardless of
whether an API key is present.

`complete()` is the only place in refereekit that calls a backend
directly, and every path a manuscript could take to a model runs through
it: the referee report and editor letter (`drafts.py:123,160`), the review
loop's summary and its question-answering (`agent/loop.py:27,103`), and
the OpenReview form-filler, which drafts through that same
`drafts.report`. So do the author responses `or-responses` reads back and
sends for comparison against your own review, on the same path as the
manuscript itself (`openreview/responses.py:29-35`). One gate, checked in
one place, covers all of them.

## The attestation

`REFEREEKIT_ZERO_RETENTION=1` is an attestation you make, not something
refereekit verifies. `_backend()` reads only the flag, not which account
or deployment it is paired with (`cli.py:34`): set it, and the backend
built for any deployment comes back marked zero-retention, whether or not
that deployment's account is actually configured that way. What you are
attesting differs by deployment, because the account behind the client
differs:

| Deployment | What `REFEREEKIT_ZERO_RETENTION=1` asserts |
|---|---|
| `anthropic` | Your organisation has a zero-data-retention arrangement. |
| `bedrock` | Your AWS account has no model-invocation logging. |
| `vertex` | Your project's logging and retention settings permit it. |

On the cloud deployments — `bedrock` and `vertex` — the provider, not
Anthropic, is the data processor, so it is that provider's own terms and
configuration the flag stands for. `anthropic` is the default only because
it is the deployment a referee with an API key already has, not because
its attestation is easier to get right — every row above is equally
unverified by refereekit itself. See [Environment
variables](../reference/environment.md) for how each deployment is chosen
and configured.

## The venue gate

Some venues forbid sending a submission to any outside model at all, and
zero-retention terms do not create an exception — the rule is about sharing
the submission at all, not about how well the transport behaves. refereekit
checks this before the attestation above: `assert_llm_permitted` runs
before a backend is built, in every command that could build one —
`draft` (`cli.py:159`), `editor` (`cli.py:175`), `review` (`cli.py:221`,
before the PDF is even opened), `or-draft` (`cli.py:352`), and
`or-responses` (`cli.py:410`).

The venue comes from `--venue` if you passed it, otherwise from a
`--spec` file's own venue, otherwise from whatever the session's
`state.json` already records — the top-level venue `or-fetch` wrote, or the
venue inside the verdict an earlier `review` saved (`cli.py:39-47`) — so a
session either command built carries its venue's rule automatically, with
nothing to restate on the command line. The built-in table has exactly one
entry (`policy.py:32-34`), and the default is to permit: code cannot know
every venue's policy, and refusing every venue it does not recognise would
make refereekit useless for the long tail of journals (`policy.py:10-14`).
This table makes the prohibitions you already know about impossible to
forget; it does not discover new ones — check what your own venue actually
forbids in [Before you start](../before-you-start.md).

```bash
refereekit review tests/fixtures/real_paper.pdf --session work/neurips --venue NeurIPS.cc/2026/Conference
```

```text
review failed: NeurIPS.cc/2026/Conference prohibits sending the submission to an outside model, so this command will not send it. Use the venue's own review interface. If this rule has changed, override it with a REFEREEKIT_VENUE_POLICY file containing:  [venues]
    "NeurIPS.cc/2026/Conference" = { llm = true }
```

Also exit code 2, and also before anything is opened: this refusal creates
no `work/neurips` session directory at all, because `assert_llm_permitted`
raises before `review` creates one. As of this version the printed key does
not lift the gate — key the override on the bare venue name; see [Before you
start](../before-you-start.md#refereekit-knows-about-one-prohibition-and-cannot-discover-others).

## The leak guard fails closed

Two checks, both in `refereekit/guard.py`, protect confidentiality once a
document is loaded. The first: an empty or unreadable document is a
rejection, not something the rest of refereekit silently works around —
`assert_no_manuscript` raises immediately if the session's document has no
extractable text at all (`guard.py:52-54`).

The second guards `mem-store`. Memory holds only notes the referee writes
themselves — a verdict, a style preference, a note for next time at the
same venue — never LLM-drafted text and never anything extracted
automatically from the manuscript. Before a note is written,
`assert_no_manuscript` checks it against the session's own document, and a
note that repeats the manuscript is refused with `mem-store failed: input
is a verbatim manuscript fragment` and, in parentheses, which of two
checks caught it: a short note (under eight words) matched against a page
exactly, or a longer one containing an eight-word run also found on a page
(`guard.py:58-62`). Either way the write is refused, exit 2, before
anything reaches `memory.db` — a note that merely quotes the paper cannot
end up stored as if it were the referee's own judgement.

## Repository rules

A session's contents are protected by exactly one line in `.gitignore` —
`/work/` (`.gitignore:75`) — because `doc.json`, `state.json`, `ours/`,
`theirs/`, and `memory.db` match no pattern of their own
(`.gitignore:11-24`). Move a session outside `work/`, or copy one of those
files out of it, and nothing else in the repository stops you from
committing a manuscript.

The only PDFs `.gitignore` lets through are the two under
`tests/fixtures/` — `real_paper.pdf` and `sample_paper.pdf`, this suite's
own fixed inputs — every other `*.pdf` is denied wherever it sits in the
tree. `style/STYLE.md`, the distilled voice guide, is committable; a raw
report never is, because it lives in `ours/`, inside a session, inside
`work/`.

Stage only what you mean to commit — never `git add -A` or `git add .` in
this repository. What keeps a manuscript out is a path (`work/`) and a set
of patterns, not a check of what a file actually contains, so a session
copied or symlinked outside `work/`, or a `--session` typed outside it by
habit, has no protection left, and a blanket add would happily stage it.
`git status` before every commit is cheap insurance against exactly that.

`.env` is read by your shell, never by refereekit: nothing in the codebase
parses it, so a credential you put there reaches `refereekit` only through
the process environment your shell already exported it into. See
[Environment variables](../reference/environment.md) for every variable
refereekit itself reads.

## The one outbound request that is not the model

`ingest`, `verify`, and `serve` never touch the network on their own.
There is one exception, and it happens only once a human opens what they
produced: the rendered Q&A page loads MathJax, so that math notation in a
model's answer typesets instead of showing as literal `$...$`, from
`cdn.jsdelivr.net`, a public CDN (`render.py:10`) — whether you open
`index.html` directly or view it through `refereekit serve`.

The browser makes that request when the page loads, not refereekit's own
process, and the script tag names one fixed file with nothing else in the
URL: no question, no answer, no manuscript text travels with it. The same
page separately polls its own address every 1.5 seconds, under `serve`,
to notice a change and reload — that request never leaves the machine,
since it goes back to `serve`'s own `127.0.0.1` listener, not to any
outside address.

## See also

- [What verification means](verification.md) — what a `PASS` or `FLAG` on
  a citation actually promises, a different question from what happens to
  the manuscript text itself, covered on this page.
- [Before you start](../before-you-start.md) — check what your own venue
  forbids before you rely on the built-in table to know it for you.
- [Environment variables](../reference/environment.md) — every variable
  named on this page, in one table, alongside what the Anthropic SDK
  reads on its own.
