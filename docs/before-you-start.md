# Before you start

This page settles the question that comes before installing anything:
whether you may send a manuscript you were asked to referee to an outside
model at all, and what refereekit will and will not do once you may.

## Your venue's rules come first, and they differ

refereekit sends manuscript text to an outside model. Whether that is
permitted is your venue's decision, not the tool's, and the venues that
have written the rule down do not agree with each other. Two examples,
each quoted from the venue's own page.

**NeurIPS 2025 prohibits it.** The "NeurIPS 2025 LLM Policy for Reviewers",
at `https://neurips.cc/Conferences/2025/LLM`, says, as of 2026-08-15: "You
must keep everything relating to the review process confidential. … Do not
talk about or share submissions with anyone or any LLMs." Zero-retention
API terms create no exception to that, because the prohibition is on
sharing at all rather than on retention: a model that keeps nothing has
still been shared with. No retention setting and no API configuration
change that. Use the venue's own review interface.

**ICLR 2026 permits it with disclosure.** "The Use of Large Language Models
(LLMs)", in the ICLR 2026 Reviewer Guide at
`https://iclr.cc/Conferences/2026/ReviewerGuide`, says, as of 2026-08-15,
that "The use of LLMs is allowed as a general-purpose writing assistance
tool", and then: "we mandate that reviewers disclose the use of LLMs in
their reviews. The review form will include a field to specify how you used
LLMs, if at all." The obligation here is not to refrain but to declare, and
that field is one you write yourself, in your own words, because a drafted
answer to a disclosure box is false in exactly the way the box exists to
prevent. ICLR 2027's reviewer guide was not yet published on that date, so
a rule read for one year is not a rule you can carry into the next.

Most venues have written nothing down at all, and where a venue is silent
the judgement is yours. These two are examples the author checked on one
date, not a table refereekit maintains and not advice about your own
assignment — open your venue's current reviewer page and read what it says
today.

## refereekit knows about one prohibition and cannot discover others

refereekit does check the venue, before it builds a backend, in every
command that could send the manuscript to a model — see
[Confidentiality](concepts/confidentiality.md#the-venue-gate) for where
that check sits. What it checks against is one line of data: the built-in
table has exactly one entry, NeurIPS (`refereekit/policy.py:32-34`).

That one entry matches generously. The venue string is lowercased and
stripped of everything that is not a letter or a digit, and the table's key
has to appear anywhere inside the result, a normalised substring match
(`refereekit/policy.py:47-49,64-72`). So the bare name `NeurIPS`, the
OpenReview id `NeurIPS.cc/2026/Conference`, and the same id for any other
year all match that one entry. Covering every year is deliberate for a
prohibition, and it means a year in which the venue changes its rule is an
override you write, not something refereekit notices.

The gate can only act on a venue it was told about: `--venue`, the venue in
a `--spec` file, or the venue `or-fetch` already recorded in the session.
Run `review` on a NeurIPS paper without naming the venue anywhere and
nothing stops the send. When it is named, the refusal looks like this:

```bash
refereekit review tests/fixtures/real_paper.pdf --session work/neurips --venue NeurIPS.cc/2026/Conference
```

```text
review failed: NeurIPS.cc/2026/Conference prohibits sending the submission to an outside model, so this command will not send it. Use the venue's own review interface. If this rule has changed, override it with a REFEREEKIT_VENUE_POLICY file containing:  [venues]
    "NeurIPS.cc/2026/Conference" = { llm = true }
```

Exit code 2, nothing sent, and no `work/neurips` directory created at all,
because the check runs before `review` opens the PDF or makes the session.

There is an override, because the table ships with the package and a
venue's policy changes without a release: `REFEREEKIT_VENUE_POLICY` points
at a TOML file that extends or overrides the built-in table. Copy the key
out of the message above, though, and it will not work. As of this version
the message names the wrong key.

A venue is looked up by walking the table in order and returning on the
first key contained in the normalised venue string, and the built-in
`neurips` is always first (`refereekit/policy.py:52-61,64-72`). Since
`neurips` is contained in `neuripscc2026conference`, that first entry
answers for the whole id, and an entry keyed on the full id — the exact
line the refusal prints — sits behind it and is never reached. Written that
way, the command still refuses.

What works is keying the override on the bare name, so it replaces the
built-in entry instead of queueing behind it. Two lines, in a file of your
own under `work/`:

```toml
[venues]
NeurIPS = { llm = true }
```

```bash
REFEREEKIT_VENUE_POLICY=work/pol.toml refereekit review tests/fixtures/real_paper.pdf --session work/neurips --venue NeurIPS.cc/2026/Conference
```

The gate is lifted and the review runs. Its last line is the ordinary one
(this run used the offline backend, so it needed no key):

```text
review complete: work/neurips/ours/report.txt, work/neurips/ours/editor.txt (2 flag(s))
```

The same trap applies to any venue the built-in table already matches: an
override only replaces an entry when its key normalises to that entry's
key. Adding a venue refereekit has never heard of is unaffected, since no
built-in key stands in front of it. The file's own example does one of
each — the bare `NeurIPS` key, which lands on the built-in entry, and a
journal that is new (`refereekit/policy.py:20-22`):

```toml
[venues]
NeurIPS = { llm = false }
"Some Journal" = { llm = false }
```

Every venue the table does not list is permitted. That default is
deliberate: refusing every venue refereekit does not recognise would make
it useless for the long tail of journals, and would be false precision,
since code cannot know a venue's policy (`refereekit/policy.py:10-14`). So
the table makes a prohibition you already know about impossible to forget
in a shell you have reused; it never discovers one for you. Keeping it
current — adding your journal, lifting a rule a venue has changed — is your
job, and that TOML file is the one place your answer gets written down
where a command will act on it.

## Confidentiality is your obligation

A manuscript you were sent to referee goes to exactly one place, and only
because you put it there: a backend you have configured and attested runs
zero-retention. refereekit refuses to send anything to a backend not marked
zero-retention, but that marking is an attestation you make about your own
account, not a fact refereekit can check for you.

A manuscript never goes into a repository either. Sessions live under
`work/`, the one directory `.gitignore` keeps out wholesale — a rule about
a path rather than a check of what a file contains, so it protects you
exactly as long as your sessions stay there and you stage named paths.

Author responses count as the same material. `or-responses` reads what the
authors wrote back and sends it to the model on the same path as the
manuscript itself (`refereekit/openreview/responses.py:29-35`), because a
rebuttal quotes and characterises the paper it defends. A venue that
forbids sending the submission forbids sending the response to it too.

[Confidentiality](concepts/confidentiality.md) has the mechanics of all
three: the single function every prompt passes through, what the
zero-retention attestation asserts on each deployment, and what
`.gitignore` does and does not cover.

## What refereekit does not do

It does not write your review. That is not modesty; it is what the commands
actually do, and each limit below is worth knowing before you lean on one.

**The verdict is yours, and it is an input.** `review` asks for your
recommendation in your own words and records it as typed; the report is
drafted from that and from the claims you verified while reading. Nothing
in refereekit recommends accepting or rejecting a paper.

**Every fixed-choice field comes back empty.** On an OpenReview form, any
field the venue gives a fixed set of choices — a rating, a confidence, a
soundness score — is left blank and listed for you to fill in, every time,
because verification here is substring matching against the page and cannot
justify a 3 over a 4 (`refereekit/openreview/form.py:45-48`).

**`or-draft` refuses a session that was never reviewed.** A session that
has been fetched but has neither verified claims nor a verdict gives the
model nothing to build the prose from, so `or-draft` exits 2 and names the
`review` command to run instead of inventing the fields and reporting
success (`refereekit/openreview/fill.py:59-77`).

**`review`, `draft` and `editor` do not refuse an empty pool.** They draft,
and then flag every anchor the drafted prose cites that the session never
established, with the reason `not in verified pool`
(`refereekit/drafts.py:98-124`). Read that asymmetry carefully, because it
inverts the reassurance you would take from a clean run: a draft with no
pool and no flags is a draft that cited nothing, not a draft that was
checked. A flag count of zero is two different outcomes wearing the same
face — every citation earned, or no citations to earn — and the count alone
cannot tell you which. What tells them apart is the claim pool the session
recorded, which you can read and re-check yourself.

That last one is the honest framing of the tool and the strongest argument
for how it is built. What refereekit hands you is not a review. It is a
pool of claims you verified yourself, prose built from that pool, and a
mark wherever the prose stepped outside it — which is worth exactly as much
as the reading you did to fill the pool. What a `PASS` in that pool
actually promises is narrower than you will assume, and [What verification
means](concepts/verification.md) says exactly how narrow.

## Next

- [Install, part 1](install.md#part-1-get-it-running), then [the
  tutorial](tutorial.md) — get the command working and watch a whole review
  run offline, with no key, no account and no manuscript.
- [Install](install.md) and then a guide — [Reviewing for a
  journal](guides/journal-review.md) or [Reviewing on
  OpenReview](guides/openreview-review.md) — once you have settled that
  your venue permits it.
