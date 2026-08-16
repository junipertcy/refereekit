# refereekit — User Documentation Design Spec

**Date:** 2026-08-15
**Author:** Tzu-Chi Yen (with Claude Code)
**Status:** Approved design → ready for implementation planning

---

## 1. Purpose

Build a user-facing documentation suite under `/docs` so that a referee who has
never seen this repository can go from finding it to producing a drafted report
without reading source code or asking the author a question.

`/docs` becomes the single home for user documentation. Nothing that a user
needs is documented in two places, because the material most likely to drift is
the safety material — retention attestations, venue policy, confidentiality —
and a stale copy of that is worse than no copy.

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
  so that a documentation change never carries a behaviour change.

---

## 2. Constraints

These are properties of this repository, not preferences. Violating any of them
produces a broken or uncommittable result.

1. **Markdown only.** `AGENTS.md` establishes a stdlib-first convention and the
   package's only runtime dependency is PyMuPDF. A `mkdocs` or `sphinx`
   dependency to render a fourteen-file suite is not justified.
2. **No file may be named `index.html`.** `.gitignore` ignores that name at
   every depth, with a single `!diagrams/index.html` exception. A documentation
   page with that name would be silently uncommittable.
3. **No manuscript-derived text, anywhere.** Every worked example uses
   `tests/fixtures/real_paper.pdf` (the author's own public paper, the only
   committable PDF) or invented placeholder text. No output from `work/`.
4. **Provider-neutral.** `anthropic`, `bedrock` and `vertex` are documented as
   peers. The direct API is the default only because it is the one a referee
   with an API key already has, and the docs say so in those terms. Bedrock in
   particular gets a fully worked setup path rather than a footnote.
5. **Stage named paths.** `.gitignore`'s manuscript patterns were re-anchored to
   an allow-list, but the standing rule in `AGENTS.md` holds: never `git add -A`
   or `git add .` in this repository.

---

## 3. Structure

```
docs/
  README.md                    index — "which path are you on?"
  before-you-start.md          may you use this at all?
  install.md                   python, venv, extras, model access, .env
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
```

### 3.1 Why this shape

The ordering is the design. A cold arrival meets three questions in a fixed
order — *am I allowed to use this?*, *does it work?*, *how do I set it up?* —
and the layered structure is the only one that can answer them in that order.
It matters here because the tutorial runs **fully offline**: no API key, no
network, no account, using the shipped fixture PDF and `REFEREEKIT_FAKE=1`.
A reader can therefore see the whole pipeline work before spending anything, and
the structure should put that experience before the setup page rather than after
it.

Small files are also a maintenance property. A single long manual is what
`README.md` is today, and its length is why its safety sections are buried.

### 3.2 Reading paths

`docs/README.md` routes the reader rather than explaining anything itself:

| Reader | Path |
|---|---|
| Evaluating the tool | `before-you-start` → `tutorial` |
| Reviewing for a journal | `before-you-start` → `install` → `guides/journal-review` |
| Reviewing on OpenReview | `before-you-start` → `install` → `guides/openreview-review` |
| Something failed | `troubleshooting` → `reference/cli` |
| Deciding whether to trust it | `concepts/verification` → `concepts/confidentiality` |

---

## 4. Page contracts

Each page states what it must contain. A page that grows beyond its contract is
a signal that the material belongs elsewhere.

### 4.1 `docs/README.md`

The routing table from §3.2, one paragraph on what refereekit is, and nothing
else. No install instructions, no commands — those exist one click away and a
duplicate here is the first thing to go stale.

### 4.2 `before-you-start.md`

The deliberate first stop, and the page that most justifies this suite existing.

It must cover, in this order:

1. **Your venue's rules come first, and they differ.** NeurIPS 2025 prohibits
   sharing submissions with any LLM outright — zero-retention API terms create
   no exception, because the prohibition is on sharing at all rather than on
   retention. ICLR 2027 permits limited use but makes disclosure mandatory, and
   its review form asks for it. Most venues are silent, and the judgment is the
   referee's.
2. **refereekit knows about one prohibition and cannot discover others.** The
   built-in table carries a single entry, NeurIPS, matched against both the bare
   name and the OpenReview id. `REFEREEKIT_VENUE_POLICY` extends it. Unlisted
   venues are permitted, because refusing the unknown would make the tool
   useless for the long tail of journals. Keeping the table current is the
   referee's job.
3. **Confidentiality is your obligation.** A submission under review is
   confidential; it goes only to a backend you have configured for
   zero-retention, and it never enters a repository.
4. **What refereekit does not do.** It does not write your review. The verdict
   is your own prose and is an input to drafting rather than an output of it;
   every field a venue defines with a fixed set of choices comes back empty,
   because substring verification cannot justify a soundness of 3 over a 4; and
   drafting refuses outright on a session with no claim pool. This is the
   honest framing and it is also the strongest argument for the design.

### 4.3 `install.md`

- Python 3.11+ (`tomllib` is a standard-library dependency of the review spec).
- `python -m venv .venv && .venv/bin/pip install -e ".[dev,llm]"`, and the
  `openreview` extra as a separate step for the OpenReview path.
- **Model access, three peer paths**, each worked end to end:
  - `anthropic` — an API key in `ANTHROPIC_API_KEY`. Default model
    `claude-opus-4-8`.
  - `bedrock` — `AWS_REGION` and `AWS_PROFILE` read by the AWS SDK, not by
    refereekit. Default model `anthropic.claude-opus-5`. An SSO-based profile
    additionally needs `pip install "botocore[crt]"`.
  - `vertex` — a real SDK client with **no confirmed default model**. It
    refuses and names `REFEREEKIT_MODEL` rather than shipping a guess.
- The two deployments with defaults name **different model generations**, and
  the page must explain why rather than leave it looking accidental: a default
  exists only where that id has actually been exercised against that
  deployment, because a fabricated id looks authoritative, gets copied into
  scripts, and fails at the provider with an error naming the model instead of
  the mistake.
- `.env` from `.env.template`, and loading it: `source scripts/load-env.fish`
  for fish, `set -a; . ./.env; set +a` for bash and zsh. refereekit reads only
  the environment and never parses `.env` itself.

### 4.4 `tutorial.md`

A complete review, offline, no key, no network. Verified to work as written.

Covers: creating the session, the summary, the Q&A loop and what an anchor is,
the verdict gate, the section-length gate, the editor-answer gate, and then a
tour of what landed in `ours/`. It shows the interactive transcript, not only
the piped one-liner, because the piped form runs the prompts together on one
line and reads as broken to someone seeing it first.

Ends by pointing at `install.md` for a real run and at
`guides/journal-review.md` for the full journey.

### 4.5 `guides/journal-review.md`

The `review` journey as a narrative: obtain the PDF, choose a session
directory, run, answer the gates, read the flags, edit the drafts. Failure
modes appear inline at the point they would occur rather than being deferred to
troubleshooting.

### 4.6 `guides/openreview-review.md`

The four-command sequence, and why it is four rather than two: `or-fetch`
downloads the paper and the form, `review` builds the verified claim pool with
you, `or-draft` writes the form's prose fields from that pool, `or-responses`
summarizes what came back. `or-draft` on a fetched-but-unreviewed session exits
2 and names the command to run, because an empty pool would mean every field
was invented while the command reported success.

Must also state: refereekit is read-only against OpenReview and contains no
`post_note_edit` call; credentials come from the environment only; one session
directory holds one paper; ratings are never filled; the review form is
discovered at runtime from the invitation; revised rebuttals arrive as new
files rather than overwriting; and a reply whose ownership cannot be confirmed
is named on stdout and held back rather than written into `theirs/`.

### 4.7 `guides/review-spec.md`

Format and motivation together. `questions` (required, non-empty), a
`[verdict]` table (`recommend`, `venue`, `major_minor`, all required), optional
`[section_lengths]` and `[editor_answers]`, and an optional top-level `venue`.
Why TOML rather than JSON or YAML. Why the spec is parsed before the backend is
built and before the PDF is opened. Why a real spec is confidential and belongs
under `work/`, never in the repository. Links to
`docs/review-spec.example.toml`, which stays where it is.

### 4.8 `guides/your-voice.md`

`style/STYLE.md` and how `--style` / `REFEREEKIT_STYLE` select one; what belongs
in a voice guide and what must never (raw report text, manuscript identifiers,
other papers' content). Then venue memory: `mem-store` requires `--session` so
the note can be checked against the manuscript, `mem-recall` returns
deduplicated notes newest-first, and notes reach `review` and `or-draft`
automatically through the shared `--db` default.

### 4.9 `guides/piecemeal.md`

The tools used alone, for a referee writing by hand who wants one capability:
`ingest` then `verify` to check a single quotation against a page; `serve` to
read a rendered Q&A page; `draft` and `editor` against a session built by other
means. Kept separate from `reference/cli.md` because this is a task, not a
lookup — the reference says what `verify` accepts, this says why you would
reach for it.

### 4.10 `reference/cli.md`

All eleven subcommands — `ingest`, `verify`, `serve`, `draft`, `editor`,
`mem-store`, `mem-recall`, `review`, `or-fetch`, `or-draft`, `or-responses` —
each with its full flag list, which flags are required, defaults, outputs, and
exit codes. Checked against `refereekit/cli.py`'s parser argument by argument.

Exit codes are a section of their own: `verify` returns 0 for PASS, 1 for FAIL
and 3 for FLAG so that calling scripts can distinguish a confirmed claim from an
unverifiable one; every other command returns 0 on success and 2 on an input
error with the reason on stderr.

### 4.11 `reference/environment.md`

Every variable, what reads it, and what happens when it is unset:
`REFEREEKIT_ZERO_RETENTION`, `REFEREEKIT_BACKEND`, `REFEREEKIT_MODEL`,
`REFEREEKIT_STYLE`, `REFEREEKIT_VENUE_POLICY`, `REFEREEKIT_FAKE`,
`REFEREEKIT_FAKE_TEXT`, `OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD`. Then the
provider-native variables refereekit never touches, read by the SDKs
themselves: `ANTHROPIC_API_KEY`, `AWS_REGION`, `AWS_PROFILE`.

### 4.12 `reference/session.md`

The directory:

```
<session>/
  paper.pdf       the submission (or-fetch only)
  doc.json        the ingested manuscript
  form.json       the venue's review form (or-fetch only)
  state.json      claim pool, verdict, and session facts
  memory.db       venue notes (default location)
  index.html      the rendered Q&A page
  ours/           drafts we generated
  theirs/         documents received from others (write-once)
```

Why `ours/` and `theirs/` are separate: a co-referee's report is evidence and
our draft is not, so searching one for a phrase that lives in the other proves
nothing. Every `state.json` key — `venue`, `number`, `forum`, `invitation_id`,
`verdict`, `claims`, `qa_count` — with what writes it.

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
  citable; section detection is best-effort and yields nothing on many papers;
  equation bodies are never reconstructed.
- What verification cannot do: it cannot tell you whether a mathematical claim
  is true. That stays human work.

### 4.14 `concepts/confidentiality.md`

The safety model end to end.

- `complete()` refuses any backend not marked `zero_retention`. Manuscript text
  reaches a model only through it.
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
- Repository rules: `work/` is git-ignored, the only committable PDF is the test
  fixture, `style/STYLE.md` is committable and raw reports never are, and never
  `git add -A` in this repository.

### 4.15 `troubleshooting.md`

Error message → cause → fix, sourced from `refereekit/` and both dogfood
reports. Must cover at least:

| Symptom | Cause |
|---|---|
| `no form.json; run or-fetch --number first` | drafting a session that was never fetched |
| `no verified claims in this session` | `or-draft` before `review` |
| `session … holds submission N` | two papers, one session directory |
| `--length names no field in this form` | flag typo, or a form that differs from the one expected |
| `no received notes in theirs/` | `or-responses` before any reply exists |
| `deployment 'vertex' has no confirmed default model` | set `REFEREEKIT_MODEL` |
| `unknown deployment …` | a `REFEREEKIT_BACKEND` typo, refused rather than defaulted |
| `refusing to send: backend is not marked zero_retention` | `REFEREEKIT_ZERO_RETENTION` unset |
| venue refusal | the venue prohibits outside models |
| `could not confirm these are not your own review` | ownership lookup returned nothing; check by hand |
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
| `README.md` | Shrinks to a landing page: what refereekit is, install, one worked command, the confidentiality rule, and a link table into `/docs`. |
| `QUICKSTART.md` | Deleted. Superseded by `docs/tutorial.md`, which covers the same ground offline and is verified. |
| `docs/DOGFOOD-FINDINGS-*.md` | Moved to `docs/internal/`. They are post-mortems and should not be the first thing a public reader meets at the top of `/docs`. |
| `docs/review-spec.example.toml` | Unchanged, referenced from `guides/review-spec.md`. |
| `docs/superpowers/` | Unchanged. |
| `AGENTS.md` | Unchanged. It is the contributor contract and stays separate from user documentation. |

---

## 6. Verification

Documentation that has not been run is a guess.

1. **Every offline command block is executed verbatim** and its real output
   pasted. That covers the whole of `tutorial.md`, the fake-backend examples,
   `ingest`, `verify`, and both memory commands. `serve` blocks, so it is
   verified by running it in the background and fetching the page, and the
   documented output is the line it prints before it starts serving.
2. **`reference/cli.md` is checked against `refereekit/cli.py`'s parser**
   argument by argument — every subcommand, every flag, every `required=True`,
   every default.
3. **`reference/environment.md` is checked against `.env.template` and every
   `os.environ` read** in the package, so neither list can be short.
4. **Anything needing a network or a key is marked as unverified** rather than
   presented as tested. That is `or-fetch`, `or-draft`, `or-responses`, and
   every real-LLM invocation.
5. **`.venv/bin/pytest` passes** before and after, so the documentation change
   is demonstrably not a behaviour change.

---

## 7. Out of scope

- A published documentation site or any CI documentation build.
- Any change to `refereekit/`, `tests/`, or `style/`. A defect found while
  writing is reported to the user, not fixed inside this task.
- Contributor documentation. `AGENTS.md` and `docs/superpowers/` already own it.
- Translations.
