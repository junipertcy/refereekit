# Troubleshooting

Find your message below: every row says what it means and what to do, and
each error refereekit prints goes to stderr behind one of four prefixes —
`error:`, `review failed:`, `mem-store failed:`, or `mem-recall failed:`.

## Install and model access

| Message | Cause | Fix |
|---|---|---|
| `error: Style guide not found: …/site-packages/style/STYLE.md` | a non-editable install — `style/` is a repository asset, not part of the installed package, so the default style path only resolves under an editable checkout | reinstall with `.venv/bin/pip install -e .`, or point past it with `--style <path>` (or `REFEREEKIT_STYLE`) |
| `error: refusing to send: backend is not marked zero_retention` | `REFEREEKIT_ZERO_RETENTION` was never exported | `export REFEREEKIT_ZERO_RETENTION=1`, after reading the row for your deployment in [Confidentiality](concepts/confidentiality.md) |
| `error: unknown deployment 'foo'; expected one of anthropic, bedrock, vertex` | a `REFEREEKIT_BACKEND` typo, refused rather than defaulted — a misspelling must not send the manuscript somewhere you did not choose | correct the spelling, e.g. `export REFEREEKIT_BACKEND=anthropic` |
| `error: deployment 'vertex' has no confirmed default model; set REFEREEKIT_MODEL to the id you want to use` | Vertex has no default model id recorded — a fabricated one would be worse than none | `export REFEREEKIT_MODEL=<the id your project serves>` |

All four exit 2, before anything is sent. See [Install, part
2](install.md#part-2-model-access-and-openreview) for how each deployment is
set up.

## Venue and confidentiality

**Message:**

```text
review failed: NeurIPS.cc/2026/Conference prohibits sending the submission to an outside model, so this command will not send it. Use the venue's own review interface. If this rule has changed, override it with a REFEREEKIT_VENUE_POLICY file containing:  [venues]
    "NeurIPS.cc/2026/Conference" = { llm = true }
```

**Cause:** the venue prohibits outside models. refereekit's built-in table
has exactly one entry and defaults every other venue to permitted, so
seeing this means the venue you named is that one entry, or one you added
yourself to a `REFEREEKIT_VENUE_POLICY` file.

**Fix:** as of this version the printed key does not lift the gate — key
the override on the bare venue name; see [Before you
start](before-you-start.md#refereekit-knows-about-one-prohibition-and-cannot-discover-others).
Otherwise use the venue's own review interface, as the message says.

Printed as `review failed: …` under `review`; as `error: …` under `draft`,
`editor`, `or-draft`, and `or-responses` — the same gate runs in all five,
before the PDF is opened and before a backend is built. All five exit 2.

## Review and drafting

| Message | Cause | Fix |
|---|---|---|
| `review failed: <spec path>: 'questions' is empty; a review that asks nothing leaves an empty claim pool and the draft would have nothing verified to cite`<br>`review failed: <spec path>: no 'verdict' table`<br>`review failed: <spec path>: verdict is missing <keys>` | the review spec is incomplete — `questions` must be non-empty, and `[verdict]` must be present with `recommend`, `venue`, and `major_minor` all filled in | add the missing key; see [Driving a review from a spec](guides/review-spec.md#spec-format) |
| `  FLAG <kind> (<anchor>): not in verified pool` | the draft cites a page or equation your question-and-answer transcript never established | ask about it directly in `review`'s question loop so it earns a place in the claim pool, or cut the sentence — see [Reviewing for a journal](guides/journal-review.md#read-the-flags) |
| `  FLAG <kind> (<anchor>): failed re-verification` | the pool predates a re-fetched `doc.json`, or the drafting model altered the quoted words when it wrote the citation into its own prose | check the sentence by hand against the current PDF — see [What verification means](concepts/verification.md#the-two-draft-flags) |

The spec row exits 2, before the PDF is opened and before a session
directory is created; fix the spec and run the same command again. The two
flag rows exit 0 — under `draft`, `editor`, or `review` alike, a flag is a
count of citations to check, not a failure.

## Memory

| Message | Cause | Fix |
|---|---|---|
| `mem-store failed: input is a verbatim manuscript fragment (short verbatim manuscript fragment)` | the note repeats the paper — `--text` matched the session's manuscript wording, so `mem-store` refused to write it | write the note in your own words — a verdict, what "minor" meant here, a phrasing habit — never a quotation, then re-run `mem-store`; see [Your voice](guides/your-voice.md#what-the-guard-rejects) |

Exit 2, and no row is written.

## OpenReview

| Message | Cause | Fix |
|---|---|---|
| `error: openreview support requires: pip install -e ".[openreview]"` | the `openreview` extra is not installed | `.venv/bin/pip install -e ".[openreview]"` |
| `error: set OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD` | credentials are not in the environment — an empty value counts as unset, the same as an absent one | fill in `.env`, then load it — `source scripts/load-env.fish` (fish) or `set -a; . ./.env; set +a` (bash, zsh); see [Install, your .env](install.md#your-env) |
| `error: openreview login failed for <username>` | the wrong password, or `--baseurl` unreachable | check the password, or the `--baseurl` host if you passed one, then re-run `or-fetch` |
| `error: no venue <venue>; check the venue id, e.g. ICLR.cc/2027/Conference` | not an OpenReview venue id — `--venue` takes the full path form the message shows, not a bare venue name | pass the venue's actual id, e.g. `refereekit or-fetch --venue ICLR.cc/2026/Conference --session work/<name>` |
| `error: submission <N> is not assigned to you at <venue>` | not assigned, or the submission does not exist — the API cannot tell them apart, because readers are restricted to the assigned committee | check `--number`, or list your assignments with `refereekit or-fetch --venue <venue> --session work/<name>` and no `--number` |
| `error: no form.json; run or-fetch --number first` | two causes: the session was never fetched with `--number`, or `or-fetch` ran before the review stage opened and printed `no review form at <venue>/Submission<N>/-/Official_Review (<reason>); skipping form.json` at the time | re-run `refereekit or-fetch --venue <venue> --number <N> --session work/<name>` — now, or once the review stage has opened |
| `error: no verified claims in this session; run refereekit review <session>/paper.pdf --session <session> first` | `or-draft` before `review` — the prose is built from the claim pool a `review` pass leaves behind, and a fetched-only session has none | run the named command, e.g. `refereekit review work/<name>/paper.pdf --session work/<name>` |
| `error: session <dir> holds submission N, not M; use a fresh --session directory for a different paper` | two papers, one session directory — the session already recorded a different submission number | use a fresh `--session` per submission, e.g. `work/iclr-42`, `work/iclr-43` |
| `error: --length takes name=value, e.g. --length summary=short` | a `--length` flag with no `=` | pass `name=value`, e.g. `--length summary=short` |
| `error: --length names no field in this form: <names>` | a `--length` name that matches nothing on the fetched form — a flag typo, or a form that differs from the one you expected | check the field names against the `to fill in yourself:` list a successful `or-draft` prints |
| `error: no received notes in theirs/; nothing to analyze` | `or-responses` before any reply exists — `theirs/` is empty | run `or-fetch --number` again once a reply has been posted |
| `could not confirm these are not your own review, so they were not stored in theirs/:`<br>`  <note-id>-<tcdate>.txt`<br>`check them by hand on forum <forum>` | the lookup for your own anonymous reviewer groups at this submission returned nothing, so refereekit cannot tell your review from a co-referee's and holds every signed-by-a-group `Official_Review` back rather than guess | nothing to fix in refereekit — open the named forum and check each note by hand; the rest of the discussion still arrives |

Every row above except the last exits 2, with the message on stderr. The
last is not an error: it prints to stdout, and `or-fetch` still exits 0.

## Verification surprises

**Message:** `FAIL: equation (<N>) is outside the range extraction can vouch
for (<A>-<B>)` — for example, against [the tutorial](tutorial.md)'s session:

```bash
refereekit verify --session work/tutorial --kind equation --anchor 18 --text ""
```

```text
FAIL: equation (18) is outside the range extraction can vouch for (1-7)
```

**Cause:** the equation really was extracted — this is not a transcription
slip — but its number falls outside the unbroken run starting at 1 that
extraction can vouch for, so it is treated as unciteable rather than
joining the claim pool as a `FLAG`.

**Fix:** nothing to fix in the citation. Cite an anchor inside the vouched
range, check the equation by hand against the PDF, or describe it without
relying on the anchor number. Exit 1, the same as any other FAIL — see
[What verification means](concepts/verification.md#extraction-limits).

**Message:** `FLAG: page <N> exists; no quotation to verify: <K> words,
need 4` — for example:

```bash
refereekit verify --session work/tutorial --kind page --anchor 2 --text "model"
```

```text
FLAG: page 2 exists; no quotation to verify: 1 words, need 4
```

**Cause:** the quoted text is under four words. `verify` never returns
`PASS` for a `quote` or `page` claim that short, however correctly it is
transcribed — a short string collides with the page by accident too easily
to carry a claim.

**Fix:** nothing to fix. Quote at least four words if you want the exact
wording checked, or accept it as an unverified pointer — the page is still
confirmed to exist, which is what a `FLAG` on this kind of claim always
guarantees. Exit 3 — see [What verification
means](concepts/verification.md#floors).

Both checks also run automatically, inside `review`'s question-and-answer
loop and again inside `draft` and `editor`; see [What verification
means](concepts/verification.md#quotation-scoped) for what running `verify`
by hand shows about those automatic passes.

## What exit 2 leaves behind

An exit 2 does not guarantee an empty session directory. `or-fetch`
validates what it can before writing anything: a download that is not a
PDF at all is refused before `paper.pdf` is created, because only the
magic bytes distinguish a paper from an HTML error page, which the PDF
reader would otherwise sniff and ingest as a one-page document. But a file
that does start with `%PDF` and is then found malformed is written to disk
first and fails during ingestion, so that one leaves `paper.pdf` behind on
exit 2. Read the message rather than the presence of files — re-fetching
into the same session is the right move either way; see [Reviewing on
OpenReview](guides/openreview-review.md#what-a-fetch-writes-and-prints) for
the write order in full.

## See also

- [Command reference](reference/cli.md) — every flag, every printed line,
  and every exit code, command by command.
- [What verification means](concepts/verification.md) — what a `PASS`,
  `FAIL`, and `FLAG` promise, and the two draft flags in full.
- [Reviewing on OpenReview](guides/openreview-review.md) — the four
  OpenReview commands run end to end, with the same errors in context.
