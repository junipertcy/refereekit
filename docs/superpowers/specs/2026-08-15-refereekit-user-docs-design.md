# refereekit — User Documentation Design Spec

**Date:** 2026-08-15
**Author:** Tzu-Chi Yen (with Claude Code)
**Status:** Approved design, revised after review on 2026-08-15 → ready for
implementation planning

---

## 0. Before this work starts

Three things this spec relies on are not in the repository yet. Each lands
first, as its own commit, so that the documentation branch is documentation
only and the before/after test run in §6.5 means what it says.

1. **The `profile_id` fix in `refereekit/openreview/client.py`**, with its
   tests in `tests/openreview_fakes.py` and `tests/test_or_client.py`. It reads
   our own id from `client.profile.id`, which login already established,
   instead of calling `get_profile()` bare — openreview-py v2 sends an empty
   query for that and the API answers 400. Without it `or-fetch`'s assignment
   listing, the entry point the OpenReview guide documents, fails against every
   venue.
2. **`AGENTS.md`**, with two corrections before it is committed: its "Known
   gap" paragraph still says the manuscript patterns in `.gitignore` are
   root-anchored, which commit 7fd6a9e fixed (they are an allow-list now), so
   the paragraph is reduced to what remains true — stage named paths, never
   `git add -A` — and why; and its "only committable PDF" line becomes "the two
   fixture PDFs". Nothing else in it changes.
3. **`scripts/load-env.fish`**, which `.env.template` and `install.md` both
   tell the reader to source.

---

## 1. Purpose

Build a user-facing documentation suite under `/docs` so that a referee who has
never seen this repository can go from finding it to producing a drafted report
without reading source code or asking the author a question.

`/docs` becomes the single home for user documentation. Nothing that a user
needs is documented in two places, because the material most likely to drift is
the safety material — retention attestations, venue policy, confidentiality —
and a stale copy of that is worse than no copy. The rule binds the root
`README.md` too (§5).

### 1.1 Audience

A referee anywhere on the internet: someone who reviews papers, is comfortable
in a terminal, and has none of this project's context. The docs must stand
alone. That decision sets the scope of several pages that would otherwise be
unnecessary — obtaining model access, understanding what zero-retention means,
and deciding whether their venue permits this at all.

### 1.2 Non-goals

- No published documentation site, no static-site generator, no CI docs build.
- No API/autodoc reference for the Python modules. `refereekit` is documented
  as a command-line tool; the module API is a contributor concern and stays in
  `AGENTS.md` and `docs/superpowers/`.
- No code changes. A defect discovered while writing is reported, not fixed,
  so that a documentation change never carries a behaviour change. The defects
  already known from the review are listed in §7 so they are not rediscovered.

---

## 2. Constraints

These are properties of this repository, not preferences. Violating any of them
produces a broken, misleading or uncommittable result.

1. **Markdown only.** `AGENTS.md` establishes a stdlib-first convention and the
   package's only runtime dependency is PyMuPDF. A `mkdocs` or `sphinx`
   dependency to render a fifteen-file suite is not justified.
2. **No file may be named `index.html`.** `.gitignore` ignores that name at
   every depth, with a single `!diagrams/index.html` exception. A documentation
   page with that name would be silently uncommittable.
3. **No manuscript-derived text, anywhere.** Every worked example uses
   `tests/fixtures/real_paper.pdf` — the author's own public paper — or
   invented placeholder text. No output from `work/`. The only committable PDFs
   are the two fixtures (`real_paper.pdf` and the synthetic
   `sample_paper.pdf`), which `.gitignore` allows by name.
4. **Provider-neutral.** `anthropic`, `bedrock` and `vertex` are documented as
   peers. The direct API is the default only because it is the one a referee
   with an API key already has, and the docs say so in those terms. Bedrock and
   Vertex each get a fully worked setup path rather than a footnote; Vertex's
   is marked unverified, because no model id has been run against it (§4.3).
5. **Stage named paths.** `.gitignore`'s manuscript patterns were re-anchored to
   an allow-list, but the standing rule in `AGENTS.md` holds: never `git add -A`
   or `git add .` in this repository.
6. **Editable install only.** `_DEFAULT_STYLE` in `refereekit/cli.py` resolves
   `style/STYLE.md` relative to the package file, so a non-editable
   `pip install .` puts the default under `site-packages`, and `review`,
   `draft` and `editor` then fail with `Style guide not found` unless `--style`
   is passed. Every documented install is `pip install -e`, and `install.md`
   says why.
7. **Sessions live under `work/`.** `.gitignore` ignores `*.pdf`, `index.html`
   and `/work/`. It does not ignore `doc.json`, `state.json`, `ours/`,
   `theirs/` or `memory.db`, all of which hold manuscript-derived text, so a
   session anywhere else in the clone is committable by `git add -A`. Every
   documented example uses `work/<name>` — the tutorial too, although its input
   is public, because the habit is the point.
8. **Facts about third parties carry a source and a date.** A venue's LLM
   policy is stated with the URL it was read from and an "as of" date, because
   it changes without this repository noticing, and the suite's own thesis is
   that a stale safety statement is worse than none.

---

## 3. Structure

```
docs/
  README.md                    index — "which path are you on?"
  before-you-start.md          may you use this at all?
  install.md                   part 1: get it running · part 2: model access
  tutorial.md                  a complete review offline — no key, ~10 min
  guides/
    journal-review.md          the `review` journey end to end
    openreview-review.md       or-fetch → review → or-draft → or-responses
    review-spec.md             non-interactive runs (format + how-to)
    your-voice.md              STYLE.md + venue memory
    piecemeal.md               ingest / verify / serve / draft / editor alone
  reference/
    cli.md                     every command, flag, exit code
    environment.md             every environment variable
    session.md                 directory layout + state.json
  concepts/
    verification.md            anchors, claim pool, PASS/FAIL/FLAG, limits
    confidentiality.md         the safety model end to end
  troubleshooting.md           error message → cause → fix
  internal/                    dogfood post-mortems (moved, not user docs)
```

Fifteen user pages. `docs/review-spec.example.toml` stays where it is;
`docs/superpowers/` is unchanged.

### 3.1 Why this shape

The ordering is the design. A cold arrival meets three questions in a fixed
order — *am I allowed to use this?*, *does it work?*, *how do I set it up?* —
and the layered structure is the only one that can answer them in that order.

It matters here because the tutorial runs offline. After the one-time part 1
of `install.md` — a clone, a venv and `pip install -e .`, the only step that
touches the network — it needs no API key, no account and makes no network
call: `REFEREEKIT_FAKE=1` and the shipped fixture PDF carry the whole pipeline.
(The rendered Q&A page loads MathJax from a CDN when opened in a browser; that
is the page, not refereekit, and no page content is sent.) A reader can
therefore see the whole pipeline work before choosing a model provider, and the
structure puts that experience before the model-access half of the setup page
rather than after it. `install.md` is split into two parts for exactly this
reason, so the tutorial can point at part 1 without repeating it.

Small files are also a maintenance property. A single long manual is what
`README.md` is today, and its length is why its safety sections are buried.

### 3.2 Reading paths

`docs/README.md` routes the reader rather than explaining anything itself:

| Reader | Path |
|---|---|
| Evaluating the tool | `before-you-start` → `install` (part 1) → `tutorial` |
| Reviewing for a journal | `before-you-start` → `install` → `guides/journal-review` |
| Reviewing on OpenReview | `before-you-start` → `install` → `guides/openreview-review` |
| Something failed | `troubleshooting` → `reference/cli` |
| Deciding whether to trust it | `concepts/verification` → `concepts/confidentiality` |

---

## 4. Page contracts

Each page states what it must contain. A page that grows beyond its contract is
a signal that the material belongs elsewhere. Where a contract quotes an error
message or an output line, the string is the one the code prints today; §6
checks it.

### 4.1 `docs/README.md`

The routing table from §3.2, one paragraph on what refereekit is, and a second
small table listing the pages the reading paths do not reach — routing, not
explanation. No install instructions, no commands — those exist one click away
and a duplicate here is the first thing to go stale.

### 4.2 `before-you-start.md`

The deliberate first stop, and the page that most justifies this suite existing.

It must cover, in this order:

1. **Your venue's rules come first, and they differ.** NeurIPS 2025 prohibits
   sharing submissions with any LLM outright — zero-retention API terms create
   no exception, because the prohibition is on sharing at all rather than on
   retention. ICLR 2026 permits LLMs "as a general-purpose writing assistance
   tool" and mandates that reviewers disclose their use in a field of the
   review form. Most venues are silent, and the judgment is the referee's.
   Each statement carries the URL it was read from and an "as of" date (§2.8),
   and the page says that these are examples the author checked on that date,
   not a table refereekit maintains. Checked 2026-08-15: the NeurIPS rule is
   the "LLM Policy for Reviewers" at `https://neurips.cc/Conferences/2025/LLM`
   ("Do not talk about or share submissions with anyone or any LLMs"); the
   ICLR rule is "The Use of Large Language Models (LLMs)" at
   `https://iclr.cc/Conferences/2026/ReviewerGuide`. ICLR 2027's reviewer
   guide was not yet published on that date, so the page cites 2026 and says
   so; the earlier draft's "ICLR 2027" was this policy misdated.
2. **refereekit knows about one prohibition and cannot discover others.** The
   built-in table carries a single entry, NeurIPS, matched against both the bare
   name and the OpenReview id — and against every year of it, so a later year's
   change of rule is an override the referee writes, not something the tool
   notices. `REFEREEKIT_VENUE_POLICY` extends it. Unlisted venues are permitted,
   because refusing the unknown would make the tool useless for the long tail
   of journals. Keeping the table current is the referee's job.
3. **Confidentiality is your obligation.** A submission under review is
   confidential; it goes only to a backend you have configured for
   zero-retention, and it never enters a repository. Author responses count:
   `or-responses` sends the replies in `theirs/` on the same path.
4. **What refereekit does not do.** It does not write your review. The verdict
   is your own prose and is an input to drafting rather than an output of it;
   every field a venue defines with a fixed set of choices comes back empty,
   because substring verification cannot justify a soundness of 3 over a 4;
   and `or-draft` refuses a session that holds neither verified claims nor a
   verdict, naming the `review` command to run. The other drafting commands do
   not refuse: `review`, `draft` and `editor` will draft from an empty pool, and
   every anchor in the result is then flagged `not in verified pool` — so a
   draft with no pool and no flags is a draft that cited nothing, not a draft
   that was checked. This is the honest framing and it is also the strongest
   argument for the design.

### 4.3 `install.md`

Two parts, because the tutorial needs only the first.

**Part 1 — get it running.**

- `git clone`, then Python 3.11+ (`tomllib` is a standard-library dependency of
  the review spec).
- `python -m venv .venv && .venv/bin/pip install -e .` — editable, and the page
  says why (§2.6). This is the only step that needs the network, and it is all
  the tutorial needs: the fake backend imports no SDK.

**Part 2 — model access and OpenReview.**

- The extras: `.[llm]` for the Anthropic SDK, `.[openreview]` for
  `openreview-py`. `dev` is pytest and is for running the suite (§6.5), not for
  reviewing; the page does not put it in the referee's install line.
- **Model access, three peer paths**, each worked end to end:
  - `anthropic` — an API key in `ANTHROPIC_API_KEY`. Default model
    `claude-opus-4-8`.
  - `bedrock` — `pip install "anthropic[bedrock]"` in addition to `.[llm]`,
    because the `llm` extra installs the SDK alone and boto3/botocore are the
    SDK's own extra. `AWS_REGION` and `AWS_PROFILE` are read by the AWS SDK,
    not by refereekit. Default model `anthropic.claude-opus-5`. An SSO-based
    profile additionally needs `pip install "botocore[crt]"`.
  - `vertex` — `pip install "anthropic[vertex]"`; `CLOUD_ML_REGION`,
    `ANTHROPIC_VERTEX_PROJECT_ID` and Google Application Default Credentials
    (`gcloud auth application-default login`, or
    `GOOGLE_APPLICATION_CREDENTIALS`) are read by the SDK. A real SDK client
    with **no confirmed default model**: it refuses and names `REFEREEKIT_MODEL`
    rather than shipping a guess. The whole path is documented from the SDK's
    own code and marked unverified (§6.4).
- The two deployments with defaults name **different model generations**, and
  the page must explain why rather than leave it looking accidental: a default
  exists only where that id has actually been exercised against that
  deployment, because a fabricated id looks authoritative, gets copied into
  scripts, and fails at the provider with an error naming the model instead of
  the mistake.
- What `REFEREEKIT_ZERO_RETENTION=1` asserts is in `concepts/confidentiality.md`;
  this page links to it and does not repeat it.
- `.env` from `.env.template`, and loading it: `source scripts/load-env.fish`
  for fish, `set -a; . ./.env; set +a` for bash and zsh. Those are the recipes
  given; a PowerShell user sets the variables by hand, and the page says so.
  refereekit reads only the environment and never parses `.env` itself.

### 4.4 `tutorial.md`

A complete review, offline, no key, no account. Verified to work as written.

Its first line says it needs part 1 of `install.md` and nothing more, and
links there. The session is `work/tutorial` (§2.7).

The fake backend returns the same string for the summary, every answer, the
report and the letter, and the tutorial says so up front. That string is
therefore chosen to demonstrate all three verdicts in one turn:

    REFEREEKIT_FAKE_TEXT='On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".'

The p. 1 quotation is on page 1 of the fixture and PASSes into the pool; the
bare `Page 2` pointer FLAGs and enters the pool; the p. 3 quotation FAILs and is
kept out. The report and the letter, being the same string, each raise one flag
— `page (3): not in verified pool` — which is the tutorial's demonstration of
what a flag is. One citation per sentence, citation before its quotation:
attribution is sentence-scoped, and a bare pointer standing between a quotation
and a trailing citation is misattributed. Verified on 2026-08-15: `state.json`
holds exactly two claims and the run reports 2 flags.

Covers: creating the session, the summary, the Q&A loop and what an anchor is
(the answer line ends `⚠ CITATION FAILED: page (3); unquoted, not verified:
page (2)`), the blank line that ends the loop, the verdict gate, the
section-length gate, the editor-answer gate, then a tour of what landed:
`ours/report.txt`, `ours/editor.txt`, `state.json`'s two claims, and
`index.html` through `serve`. After the run, the three `verify` calls that
reproduce the three verdicts by hand, with their exit codes 0, 1 and 3.

It shows the interactive transcript, not only the piped one-liner, because the
piped form runs the prompts together on one line and reads as broken to someone
seeing it first. The piped form is what §6.1 executes; the interactive
transcript is reconstructed from it — prompts and typed answers on their own
lines — and the page says the two differ only in layout.

Ends by pointing at part 2 of `install.md` for a real run and at
`guides/journal-review.md` for the full journey.

### 4.5 `guides/journal-review.md`

The `review` journey as a narrative: obtain the PDF, choose `work/<name>`,
decide on `--venue`, run, answer the gates, read the flags, edit the drafts.
Failure modes appear inline at the point they would occur rather than being
deferred to troubleshooting.

`--venue` does two things and is otherwise optional: it is what the venue
policy gate reads, and it is what opens venue memory — without it no store is
opened at all. Memory's `--db` default is `<session>/memory.db`, which is
per-session; a referee who wants notes to carry across papers passes one shared
path — the guide uses `work/memory.db` — on every command that takes `--db`
(§4.8). The flags a draft can carry are two, and the guide says what each
means: `not in verified pool` (the draft cited an anchor the Q&A never
established) and `failed re-verification` (it was in the pool but no longer
verifies against `doc.json`). `--spec` and `--style` are pointers to their
guides, not repeated here.

### 4.6 `guides/openreview-review.md`

Opens with the entry point: `pip install -e ".[openreview]"`, credentials in
the environment, then `or-fetch --venue <id>` with **no** `--number`, which
lists the papers assigned to you and names any it could not read.

Then the four-command sequence, and why it is four rather than two: `or-fetch
--number` downloads the paper and the form, `review` builds the verified claim
pool with you, `or-draft` writes the form's prose fields from that pool,
`or-responses` summarizes what came back. `or-draft` on a fetched-but-unreviewed
session exits 2 and names the command to run, because an empty pool would mean
every field was invented while the command reported success.

Must also state:

- refereekit is read-only against OpenReview and contains no `post_note_edit`
  call; credentials come from the environment only; `--baseurl` points at the
  API sandbox for a dry run.
- The form and the discussion are best-effort: before the review stage opens,
  `or-fetch` prints `no review form at …; skipping form.json` and exits 0, and
  before any reply exists it prints `no replies yet; theirs/ left empty`. A
  later `or-fetch --number` of the same paper picks them up.
- One session directory holds one paper; re-fetching the same number is how a
  new rebuttal is picked up — and it also re-downloads and re-ingests the PDF,
  so `paper.pdf` and `doc.json` become the current version while the claims in
  `state.json` were verified against the earlier one. A revised manuscript can
  turn a verified quotation into `failed re-verification` on the next draft.
- Ratings are never filled; the review form is discovered at runtime from the
  invitation, and a field is classified by whether it has fixed choices, not by
  its name — so **every free-text field is drafted**, including a confidential
  comment to the area chairs and any LLM-usage or self-assessment textbox a
  venue adds. Those the referee rewrites by hand; a disclosure box in
  particular must be the referee's own words. The guide points back to
  `before-you-start` for the venue's disclosure rule.
- Revised rebuttals arrive as new files rather than overwriting; a reply whose
  ownership cannot be confirmed is named on stdout and held back rather than
  written into `theirs/`.

### 4.7 `guides/review-spec.md`

Format and motivation together. `questions` (required, non-empty), a
`[verdict]` table (`recommend`, `venue`, `major_minor`, all required), optional
`[section_lengths]` and `[editor_answers]`, and an optional top-level `venue`
that falls back to `[verdict].venue` — so a verdict naming the venue drives the
policy gate and memory without the top-level key. Why TOML rather than JSON or
YAML. Why the spec is parsed before the backend is built and before the PDF is
opened. Why a real spec is confidential and belongs under `work/`, never in the
repository. Links to `docs/review-spec.example.toml`, which stays where it is.

### 4.8 `guides/your-voice.md`

`style/STYLE.md` and how `--style` / `REFEREEKIT_STYLE` select one; what belongs
in a voice guide and what must never (raw report text, manuscript identifiers,
other papers' content).

Then venue memory, precisely, because the defaults are easy to misread:
`mem-store` requires `--session` so the note can be checked against the
manuscript, and its `--db` defaults to `<session>/memory.db`; `mem-recall`
requires `--db`; `review` and `or-draft` default to `<session>/memory.db` and
open no store unless a venue is known. That default is per-session, so notes
carry across papers only when every command is given the same `--db` path — the
guide recommends `work/memory.db` and shows it on every command. `draft` and
`editor` never read memory. Recall is deduplicated by exact text, newest first,
capped by `--limit` (default 20).

What the guard rejects, in the referee's terms: any verbatim fragment of the
session's manuscript — a short exact match, an eight-word run, or more than one
shared eight-word window — with the message it prints; and it refuses outright
against a session whose document has no text.

### 4.9 `guides/piecemeal.md`

The tools used alone, for a referee writing by hand who wants one capability:
`ingest` then `verify` to check a single quotation against a page; `serve` to
read the rendered Q&A page, which only `review` writes (after `ingest` alone the
page is a 404); `draft` and `editor` against a session built by other means —
they take no `--db`, read no memory, and do not refuse an empty pool: they flag
every anchor instead. Kept separate from `reference/cli.md` because this is a
task, not a lookup — the reference says what `verify` accepts, this says why
you would reach for it.

### 4.10 `reference/cli.md`

All eleven subcommands — `ingest`, `verify`, `serve`, `draft`, `editor`,
`mem-store`, `mem-recall`, `review`, `or-fetch`, `or-draft`, `or-responses` —
each with its full flag list, which flags are required, defaults, outputs, and
exit codes. Checked against `refereekit/cli.py`'s parser argument by argument;
`--help` carries almost no help strings, so the parser is the source.

Exit codes are a section of their own: `verify` returns 0 for PASS, 1 for FAIL
and 3 for FLAG so that calling scripts can distinguish a confirmed claim from an
unverifiable one; every other command returns 0 on success and 2 on an input
error with the reason on stderr — except `serve`, which runs until interrupted
and never returns 2 (a missing session directory serves 404s; an existing one
with no `index.html` serves a directory listing with HTTP 200), and which moves
to the next free port above `--port` when that one is busy, printing the port
it chose. The reference records each command's error
prefix as printed (`error:`, `review failed:`, `mem-store failed:`), the
precedence of `review`'s venue (`--venue`, then the spec's, then the
session's), and the asymmetry that `mem-store --db` is optional while
`mem-recall --db` is required.

### 4.11 `reference/environment.md`

Every variable refereekit reads, what reads it, and what happens when it is
unset: `REFEREEKIT_ZERO_RETENTION`, `REFEREEKIT_BACKEND`, `REFEREEKIT_MODEL`,
`REFEREEKIT_STYLE`, `REFEREEKIT_VENUE_POLICY`, `REFEREEKIT_FAKE`,
`REFEREEKIT_FAKE_TEXT`, `OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD`.

Then, per deployment, the variables the SDK reads and refereekit never touches:
`anthropic` — `ANTHROPIC_API_KEY`; `bedrock` — `AWS_REGION`, `AWS_PROFILE` and
the rest of the AWS credential chain; `vertex` — `CLOUD_ML_REGION`,
`ANTHROPIC_VERTEX_PROJECT_ID`, and Google Application Default Credentials. The
Vertex entries are marked as read from the SDK's code, not from a run.

### 4.12 `reference/session.md`

The directory, with what writes each entry, because most of it appears only
after a particular command:

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

Why `ours/` and `theirs/` are separate: a co-referee's report is evidence and
our draft is not, so searching one for a phrase that lives in the other proves
nothing. Every `state.json` key with what writes it: `venue`, `number`,
`forum`, `invitation_id` (`or-fetch`; `venue` also appears inside the verdict
`review` saves), `verdict` (the verdict gate), `claims` (the Q&A loop),
`qa_count` (the page renderer).

### 4.13 `concepts/verification.md`

What a `PASS` actually promises, which is narrower than a reader will assume.

- Verification is **quotation-scoped**. A `PASS` on a page or quote claim means
  these exact words, normalized for whitespace and case, are on that page. Only
  text presented as a quotation is checked.
- A citation carrying no quotation is `FLAG`, not `PASS` — the page exists, the
  wording was never checked. This is the common case, because referee prose
  paraphrases and a paraphrase cannot be substring-matched.
- `FLAG` checks the page first, so it carries a guarantee: a citation to a page
  that is not in the document is `FAIL` however little it quotes. That is what
  makes a `FLAG` safe to keep in the claim pool.
- Floors: a quoted span under 12 characters is skipped as scare-quoting, and a
  span carrying fewer than four words verifies as `FLAG`. Four words is where a
  match stops being accidental.
- Typography folding is folding, not fuzzy matching. Each rule maps two
  spellings of the same characters onto one, so a genuine misquotation still
  fails and a hyphen inside a line stays content — `58%` does not match `5-8%`.
- Extraction limits, in the same page because they are the same story: figures
  are reliable; an equation anchor passes only inside the contiguous run of
  extracted ids beginning at 1, and one outside that run is `FAIL` rather than
  `FLAG` on purpose, because a `FLAG` would enter the claim pool and stay
  citable — with the residual that a section-numbered label such as `(2.1)` is
  outside the run rule and passes on bare existence; section detection is
  best-effort and yields nothing on many papers; equation bodies are never
  reconstructed.
- The two flags a draft can carry, `not in verified pool` and `failed
  re-verification`, and what each means (§4.5).
- What verification cannot do: it cannot tell you whether a mathematical claim
  is true. That stays human work.

### 4.14 `concepts/confidentiality.md`

The safety model end to end.

- `complete()` refuses any backend not marked `zero_retention`. Manuscript text
  reaches a model only through it — and so do author responses, which
  `or-responses` sends on the same path.
- `REFEREEKIT_ZERO_RETENTION=1` is an attestation *you* make and the code
  cannot verify. What it asserts depends on where the client points, and the
  page carries the per-deployment table: on `anthropic` your organization has a
  zero-data-retention arrangement; on `bedrock` your AWS account has no
  model-invocation logging; on `vertex` your project's logging and retention
  settings permit it.
- The venue gate refuses before a backend is built and before the PDF is
  opened, reading the venue from `--venue`, the spec, or the session state that
  `or-fetch` already recorded.
- The leak guard fails closed: an empty or unreadable document is a rejection,
  not a pass, and memory stores referee-authored notes only.
- Repository rules: `work/` is git-ignored and sessions live under it, because
  `doc.json`, `state.json`, `ours/`, `theirs/` and `memory.db` are
  manuscript-derived and nothing else in `.gitignore` protects them (§2.7); the
  only committable PDFs are the two test fixtures; `style/STYLE.md` is
  committable and raw reports never are; never `git add -A` in this
  repository. `.env` is read by the shell, never parsed by refereekit.
- The one outbound request that is not the model: the rendered `index.html`
  loads MathJax from a CDN when opened in a browser. No page content is sent.

### 4.15 `troubleshooting.md`

Error message → cause → fix, sourced from `refereekit/` and both dogfood
reports. Must cover at least:

| Symptom | Cause |
|---|---|
| `Style guide not found: …/site-packages/…` | a non-editable install; reinstall with `pip install -e .`, or pass `--style` |
| `refusing to send: backend is not marked zero_retention` | `REFEREEKIT_ZERO_RETENTION` unset |
| `unknown deployment …; expected one of anthropic, bedrock, vertex` | a `REFEREEKIT_BACKEND` typo, refused rather than defaulted |
| `deployment 'vertex' has no confirmed default model` | set `REFEREEKIT_MODEL` |
| `… prohibits sending the submission to an outside model` | the venue prohibits outside models; the message shows the override |
| `mem-store failed: input is a verbatim manuscript fragment …` | the note repeats the paper; write it in your own words |
| `'questions' is empty` / `no 'verdict' table` / `verdict is missing …` | the review spec is incomplete |
| `openreview support requires: pip install -e ".[openreview]"` | the extra is not installed |
| `set OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD` | credentials not in the environment (an empty value counts as unset) |
| `openreview login failed for …` | wrong password, or `--baseurl` unreachable |
| `no venue …; check the venue id` | not an OpenReview venue id (`ICLR.cc/2027/Conference` form) |
| `submission N is not assigned to you at …` | not assigned, or nonexistent — the API cannot tell them apart |
| `no form.json; run or-fetch --number first` | two causes: the session was never fetched, or `or-fetch` ran before the review stage opened and printed `no review form at …; skipping form.json` — re-run it |
| `no verified claims in this session` | `or-draft` before `review` |
| `session … holds submission N` | two papers, one session directory |
| `--length takes name=value` / `--length names no field in this form` | flag typo, or a form that differs from the one expected |
| `no received notes in theirs/` | `or-responses` before any reply exists |
| `could not confirm these are not your own review` | ownership lookup returned nothing; check by hand |
| a draft flag `not in verified pool` | the draft cited an anchor the Q&A never established |
| a draft flag `failed re-verification` | the pool predates a re-fetched `doc.json`, or the model altered a quotation |
| an equation cites correctly but `FAIL`s | anchor outside the vouched run |
| a correct quotation `FLAG`s | under four words |

Plus the non-obvious one worth its own paragraph: **an exit 2 does not guarantee
an empty session directory.** `or-fetch` validates what it can before writing
and rejects a non-PDF download before `paper.pdf` is created, but a file that
begins with `%PDF` and is then found malformed leaves `paper.pdf` on disk. Read
the message rather than the presence of files.

---

## 5. Changes outside `/docs`

| Path | Change |
|---|---|
| `README.md` | Shrinks to a landing page: one paragraph on what refereekit is, one sentence on confidentiality that links to `docs/concepts/confidentiality.md`, and links to `docs/README.md` and `docs/before-you-start.md`. No install block and no commands: §1's rule binds the root README exactly as it binds `docs/README.md`, and install and the worked command are one click away. |
| `QUICKSTART.md` | Deleted. Superseded by `docs/tutorial.md`, which covers the same ground offline and is verified. |
| `docs/DOGFOOD-FINDINGS-*.md` | Moved to `docs/internal/`. They are post-mortems and should not be the first thing a public reader meets at the top of `/docs`. |
| `docs/review-spec.example.toml` | Unchanged, referenced from `guides/review-spec.md`. |
| `docs/superpowers/` | Unchanged. |
| `AGENTS.md` | Committed before this work with the two corrections in §0. Otherwise unchanged: it is the contributor contract and stays separate from user documentation. |
| `scripts/load-env.fish` | Committed before this work (§0). |
| `.env.template` | Its Bedrock block gains the `pip install "anthropic[bedrock]"` line, and a "Vertex deployment only" block names `CLOUD_ML_REGION` and `ANTHROPIC_VERTEX_PROJECT_ID` — read by the SDK, not yet exercised — so the template and `reference/environment.md` list the same names. Names only, no values. No test pins the template's contents. |

---

## 6. Verification

Documentation that has not been run is a guess.

1. **Every offline command block is executed verbatim** and its real output
   pasted. That covers the whole of `tutorial.md` (piped form, with the fixed
   `REFEREEKIT_FAKE_TEXT` of §4.4; the interactive transcript is a re-layout of
   that run and nothing more), the fake-backend examples, `ingest`, `verify`,
   both memory commands, and every offline-reproducible error in
   `troubleshooting.md`. `serve` blocks, so it is verified by running it in the
   background and fetching the page, and the documented output is the line it
   prints before it starts serving.
2. **`reference/cli.md` is checked against `refereekit/cli.py`'s parser**
   argument by argument — every subcommand, every flag, every `required=True`,
   every default.
3. **`reference/environment.md` is checked against three sources**, so neither
   list can be short: `.env.template`, every `os.environ` read in the package,
   and — for the variables refereekit does not read — the SDK's own reads for
   each registered deployment. `bedrock` registers `AnthropicBedrockMantle`
   (`refereekit/llm.py:61`), so its reads are in
   `anthropic/lib/bedrock/_mantle.py` plus `anthropic/lib/aws/_credentials.py`,
   not `anthropic/lib/bedrock/_client.py`; `vertex` reads are in
   `anthropic/lib/vertex/_client.py`.
4. **Anything needing a network or a key is marked as unverified** rather than
   presented as tested. That is `or-fetch`, `or-draft`, `or-responses`, every
   real-LLM invocation, and the Bedrock and Vertex setup paths.
5. **`.venv/bin/pytest` passes** before and after (354 at the baseline), so the
   documentation change is demonstrably not a behaviour change.
6. **Every relative link in `docs/` and `README.md` resolves**, checked with a
   script at the end and after each page.
7. **No session path outside `work/`** appears in any documented command, and
   `git status` before each commit shows nothing under `work/` staged.

---

## 7. Out of scope

- A published documentation site or any CI documentation build.
- Any change to `refereekit/`, `tests/`, `style/` or `pyproject.toml`. A defect
  found while writing is reported to the user, not fixed inside this task.
- Contributor documentation. `AGENTS.md` and `docs/superpowers/` already own it.
- Translations.

### 7.1 Defects already known, to be reported with the finished docs

Found during the spec review; the docs describe the behaviour as it is.

1. A non-editable install breaks the default style path (`_DEFAULT_STYLE`,
   `refereekit/cli.py`); the package should locate `STYLE.md` as package data
   or fail with a message that names the fix.
2. `or-draft` drafts every free-text field, including confidential comments to
   the chairs and any LLM-usage disclosure textbox (`refereekit/openreview/
   fill.py`, `form.py`): a disclosure box drafted by the model defeats its
   purpose.
3. Re-fetching a submission replaces `doc.json` without re-verifying the claims
   in `state.json`, and `responses.py`'s stale-manuscript note still says
   `doc.json` "holds the version originally fetched", which stops being true
   after a re-fetch.
4. `pyproject.toml` has no `bedrock` or `vertex` extras, so the docs point at
   the SDK's own (`anthropic[bedrock]`, `anthropic[vertex]`).
5. `serve` has no error handling, unlike every other command: a missing session
   directory serves 404s rather than exiting 2, and an existing session with no
   `index.html` serves a directory listing with HTTP 200 — Python's
   `SimpleHTTPRequestHandler` default (`refereekit/render.py:43-45`) — so a
   session that has only been ingested looks served rather than unready.
6. `refereekit/ingest.py:2` imports `fitz`. PyMuPDF ≥ 1.28.2 prints a `fitz`
   deprecation warning to stdout before every command's output; the repo
   `.venv` at 1.28.0 is silent, so the warning shows up only on a fresh
   install, and it lands on stdout rather than stderr.
7. `refereekit/policy.py:75-83`: the refusal message names an override keyed on
   the full venue id, which the built-in `neurips` entry shadows — `_table()`
   (52-61) puts the built-in first and `llm_permitted` (64-72) returns on the
   first key contained in the normalised venue. Only a bare-name override
   works, so the message as printed cannot lift the gate it describes.
8. `review` reads `--style`/`REFEREEKIT_STYLE` only when it starts drafting
   (`refereekit/agent/loop.py:36`, `refereekit/drafts.py:121`), after the
   manuscript has already been sent. The path should be validated before the
   first `complete()`, so a typo costs nothing.
9. `drafts.report()` calls `complete()` before `session.load_doc()`
   (`refereekit/drafts.py:123-124`), so `draft` on a session with no `doc.json`
   makes a model call before failing.
10. `or-draft`'s venue gate reads only the top-level `venue` state key
    (`refereekit/cli.py:352`), while `draft`, `editor`, `or-responses` and
    `review` go through `_session_venue` (`cli.py:39-47`), which also reads the
    venue inside a saved verdict. Unobservable through the documented flow
    today, because every `or-draft` session was fetched by `or-fetch`, which
    writes the top-level key.
11. `scripts/load-env.fish` exported every single-quoted `.env` value as the
    literal string `$1`: the replacement was written `'\$1'`, which
    `string replace -r` reads as an escaped dollar rather than a capture group.
    Fixed on this branch, since it is a documented command in `install.md`.
12. `pyproject.toml`'s `llm` extra installs the Anthropic SDK alone. Bedrock
    additionally needs `anthropic[bedrock]` and Vertex `anthropic[vertex]`,
    which is why the docs point at the SDK's own extras (item 4, stated
    precisely).
