# refereekit

Standalone, harness-portable toolkit that automates a paper-review workflow.

> **New here?** See **[QUICKSTART.md](QUICKSTART.md)** — the one-command way to review a
> paper. This README documents every individual tool and the build phases behind them.

## Confidentiality
Confidential manuscripts and text derived from them are never committed. The only
committable PDF is the test fixture under `tests/fixtures/`. Manuscript text is
guarded: it only flows to LLM backends explicitly configured with zero-retention.
The distilled `style/STYLE.md` voice guide is committable; raw reports are never
committed or sent to any service.

## Install
    python -m venv .venv && .venv/bin/pip install -e ".[dev,llm]"

## Use

### Phase 1 (SP-A): Ingest, Verify, Serve
    refereekit ingest paper.pdf --session ./work/paperA
    refereekit verify --session ./work/paperA --kind quote --anchor 16 --text "5-8%"
    refereekit serve  --session ./work/paperA --port 8888

### Session layout

    <session>/
      doc.json        the ingested manuscript
      state.json      claim pool and verdict
      ours/           drafts we generated (report.txt, editor.txt)
      theirs/         documents received from others (write-once)

`ours/` and `theirs/` are separate because they are different kinds of thing.
A co-referee's report is evidence; our own draft is not. Searching one for a
phrase that lives in the other proves nothing, and a `report.txt` sitting
loose in the session root gives no way to tell which one you are holding.

### Phase 2 (SP-B): Draft Generation
Generate referee reports and editor letters using a verified claim pool.

**Backend selection (environment variables):**
- **Offline mode (for testing):** Set `REFEREEKIT_FAKE=1` to use a fake backend that
  returns canned text without calling any API. Optionally set `REFEREEKIT_FAKE_TEXT`
  to control the returned text.
- **Real LLM (zero-retention only):** Set `REFEREEKIT_ZERO_RETENTION=1` to confirm
  zero-retention terms. Optionally set `REFEREEKIT_MODEL` (default: `claude-opus-4-8`).
  Requires the `anthropic` package: `pip install -e ".[llm]"`
- **Transport:** `REFEREEKIT_BACKEND` selects `anthropic` (default) or `bedrock`.
  Any other value is refused — a misspelled transport must not quietly become the
  default, since that would send the manuscript over a path the referee did not
  choose. Model defaults follow the transport (`claude-opus-4-8` vs
  `anthropic.claude-opus-5`), so set `REFEREEKIT_MODEL` only alongside a matching
  `REFEREEKIT_BACKEND`.

**Which transport, and what the attestation means.** `REFEREEKIT_ZERO_RETENTION=1`
is an attestation *you* make, not something the code can verify — `complete()`
only checks that the flag was set. What you are attesting differs by transport:

| Transport | Data processor | What `=1` asserts |
|---|---|---|
| `anthropic` | Anthropic | Your organization has a zero-data-retention arrangement. |
| `bedrock` | AWS | Your AWS account has no model-invocation logging configured. |

On `bedrock`, Anthropic's retention terms do not govern the request at all, so
this is the practical route when a first-party ZDR arrangement is not available.
Credentials come from the usual AWS chain and are never read by refereekit; an
SSO-based profile additionally needs `pip install "botocore[crt]"`.

**Commands:**
    # Generate a referee report
    export REFEREEKIT_ZERO_RETENTION=1
    refereekit draft --session ./work/paperA [--length intro=short ...]

    # Generate an editor response letter
    refereekit editor --session ./work/paperA --answers a=yes --answers b=no

**Output:** Draft text is written to `<session>/ours/report.txt` or `editor.txt`.
The command prints a summary including flag count. Flags indicate anchors that failed
verification (not in verified pool or failed re-verification against the document).

**Confidentiality note:** Manuscript text flows only through backends configured with
`zero_retention=True`. The `style/STYLE.md` voice guide is distilled and committable;
raw manuscript text and reports are never committed.

### Phase 3 (SP-C): Memory

Store and recall referee-authored notes across sessions. Memory is guarded:
manuscript-verbatim text can never be stored. All notes are explicitly written by the
referee — no LLM auto-distillation, no automatic extraction from manuscripts.

**Guarded write:**
- `mem-store` requires a session document to validate against. The write is rejected
  (exit 2, printed error) and nothing is stored if the input text:
  - Contains a verbatim manuscript fragment (short <8-word exact match, or ≥8-word
    contiguous run, or ≥8-word scattered n-gram overlap)
- This fail-closed design ensures manuscript confidentiality: text under review cannot
  leak into memory.

**Commands:**
    # Store a referee-authored note (requires --session to guard against manuscript text)
    refereekit mem-store --session ./work/paperA --venue PRX --kind verdict \
        --text "PRX: lean accept-after-major on approximate-but-validated theory" \
        --db ./work/memory.db

    # Recall notes for a venue (default: 20 most recent, deduplicated by normalized text)
    refereekit mem-recall --venue PRX --db ./work/memory.db

**Deduplication and recency:**
- Recall returns distinct notes (exact-text dedup), newest-first, capped at 20 notes (configurable).
- Sorted by `created_at` descending.

**Note kinds:** `verdict`, `quote`, `claim`, `method`, `style` — the `kind` field is
stored but not used for filtering in this phase.

### Phase 4 (SP-D): Standalone review

A scripted orchestrator that runs a fixed review pipeline from PDF to final report/letter,
with no external harness coordination. The pipeline runs entirely offline in fake mode, or
with a zero-retention LLM for real reviews.

**Fixed pipeline:**
1. **Ingest** — extract pages, equations, claims from the PDF
2. **Summarize** — generate a referee summary of the paper
3. **Interactive Q&A** — multi-turn question loop; answers are verified against the
   document and recorded into the claim pool
4. **Verdict gate** — prompt for recommendation, venue, major/minor (saved to session state)
5. **Draft report** — generate referee report using the verified claim pool and verdict
6. **Detail gate** — prompt for optional section length overrides
7. **Editor letter** — generate editor response letter with optional editor-question answers

**Command:**
    refereekit review <pdf> --session <dir> [--venue <venue>] [--spec <file>]

### Review specs

The gates above prompt for typed answers. A real verdict is considered prose
drafted over days, and the questions worth asking a manuscript are equally
deliberate — neither is something you compose at a `verdict (recommend)>`
prompt. `--spec` supplies all of them from a TOML file, so a review runs with no
terminal interaction:

    refereekit review paper.pdf --session ./work/paperA --spec ./work/paperA/review.toml

See **[docs/review-spec.example.toml](docs/review-spec.example.toml)** for the
full format. In brief: `questions` (required, non-empty), a `[verdict]` table
(`recommend`, `venue`, `major_minor`, all required), and optional
`[section_lengths]` and `[editor_answers]` tables. A top-level `venue` supplies
`--venue`.

TOML rather than JSON or YAML: `tomllib` is in the standard library from 3.11,
and triple-quoted strings keep a thousand-word verdict readable. JSON would put
it on one escaped line.

The spec is parsed before the backend is built and before the PDF is opened, so
a spec that cannot drive the run fails while nothing has been sent anywhere.

Keep the spec beside its session. It is the record of what you asked and what
you concluded, and it makes a review re-runnable after an ingest fix without
retyping a word. A real spec quotes the manuscript, so it is confidential —
write it under `work/`, never in the repo.

**Example (offline, no network):**
    export REFEREEKIT_FAKE=1
    export REFEREEKIT_FAKE_TEXT="Answer. See p. 1."
    printf 'q?\n\nminor\nPRX\nminor\n\n\n' | \
      refereekit review tests/fixtures/real_paper.pdf --session /tmp/review-session --venue PRX

**Real use (zero-retention LLM):**
    export REFEREEKIT_ZERO_RETENTION=1
    export REFEREEKIT_MODEL=claude-opus-4-8
    refereekit review paper.pdf --session ./work/paperA --venue PRX

**Output:** Writes `<session>/ours/report.txt`, `<session>/ours/editor.txt`, and `<session>/index.html`.

**Confidentiality note:** Manuscript text goes **only** to the zero-retention LLM backend
during `review`. The session transcript, report, and editor letter remain in the session
directory (git-ignored). No manuscript text is sent to memory or committed.

### Phase 5 (SP-E): OpenReview

Review a paper assigned on OpenReview. Fetch the assignment and its PDF,
discover the venue's review form, draft the form's prose fields, and summarize
the authors' responses.

**Read-only.** refereekit never posts to OpenReview. There is no
`post_note_edit` call in the package. Output is written locally for you to read
and paste.

**Install:** `pip install -e ".[openreview]"`

**Credentials** come from the environment, never a flag, so a password stays out
of shell history and the process table:

    export OPENREVIEW_USERNAME=you@example.com
    export OPENREVIEW_PASSWORD=...

**Commands:**

    # list the papers assigned to you
    refereekit or-fetch --venue ICLR.cc/2027/Conference --session ./work/iclr

    # fetch one: paper.pdf, doc.json, form.json, and theirs/
    refereekit or-fetch --venue ICLR.cc/2027/Conference --number 42 \
        --session ./work/iclr-42

    # read the paper and build the verified claim pool (step 2 of 3)
    refereekit review ./work/iclr-42/paper.pdf --session ./work/iclr-42 \
        --venue ICLR.cc/2027/Conference

    # draft the prose fields
    export REFEREEKIT_ZERO_RETENTION=1
    refereekit or-draft --session ./work/iclr-42 [--length summary=short] \
        [--db ./work/memory.db]

    # summarize what the authors said back
    refereekit or-responses --session ./work/iclr-42

**`or-draft` requires a `review` pass first, in the same session directory.**
Drafting is three steps, not two: `or-fetch` downloads the paper and the form,
`review` reads the paper with you and records the verified claims and your
verdict, and `or-draft` writes the form's prose fields from that pool. There is
no shortcut, because the pool is what the prose is built from: `or-draft` on a
session that has only been fetched exits 2 and names the `review` command to
run. Running `review` into a fetched session leaves `venue`, `number`, `forum`,
and `form.json` in place, so the order above is the whole sequence.

**Output:** `ours/openreview.md` for reading and pasting, `ours/openreview.json`
as a field-name-to-value mapping, and `ours/response-analysis.txt`.

**Exit codes:** all three return 0 on success and 2 on an input error, with the
reason on stderr. An input error means a bad venue id, a submission not assigned
to you, a download that is not a pdf, a session pointed at a different paper, a
missing session, a session with no `form.json`, a session with no claim pool, an
empty `theirs/`, a malformed `--length`, or a missing optional dependency.

An exit 2 does not guarantee an empty session directory. `or-fetch` validates
what it can before writing, and rejects a download that is not a pdf before
`paper.pdf` is created, but a file that begins with `%PDF` and is then found
malformed leaves `paper.pdf` on disk. Read the message rather than the presence
of files: when `or-fetch` exits 2 after writing, the session is not a fetched
paper and re-fetching into it is the right move.

A failure to read the review form or the discussion is not an exit 2. Those
steps are best-effort: `or-fetch` prints what it could not read, leaves
`form.json` absent or `theirs/` empty, and exits 0, because the PDF is the part
you need first and a later `or-fetch` picks up the rest.

**One session directory holds one paper.** `or-fetch --number` refuses a
session whose `state.json` records a different number, because overwriting
would leave `theirs/` holding two papers' notes and a stale
`ours/openreview.md` that `or-responses` would read as your review of the new
paper. Use a fresh `--session` per submission. Re-fetching the same number into
the same session is fine, and is how you pick up a new rebuttal.

**`--db`** gives `or-draft` your memory database, mirroring `review`. `or-fetch`
records the venue in the session, so the notes you have stored for that venue
reach the draft. It defaults to `<session>/memory.db`, the same default
`review` uses, so the two commands share one store without being told to.

**`--baseurl`** points `or-fetch` at a different OpenReview deployment. It
defaults to `https://api2.openreview.net`. Use
`--baseurl https://devapi2.openreview.net` to try the calls against the API
sandbox without touching production.

**Ratings are never filled in.** Verification is quotation-scoped substring
matching. It can confirm that a quoted phrase is on a page; it cannot tell a
soundness of 3 from a 4. Every field the venue defines with a fixed set of
choices comes back empty, listed for you under "to fill in yourself".

**The review form is discovered at runtime.** An OpenReview invitation is
self-describing, so ICLR's summary/strengths/weaknesses/soundness/presentation/
contribution and the default form's title/review/rating/confidence both work
with no venue-specific code. A field is classified by whether the invitation
gives it a fixed set of choices, not by its name.

**Revised rebuttals.** Received notes are stored in `theirs/` as
`<note-id>-<tcdate>.txt`. A rebuttal edited during the discussion period has a
new timestamp and so becomes a new file: both versions are kept and you can see
what changed. Replies you signed yourself are not stored in `theirs/`, because
that directory is for documents received from others.

**A reply whose ownership cannot be confirmed is held back, not stored.**
Identifying your own replies means looking up your anonymous reviewer groups
for the submission. That lookup can fail, and a venue may name its reviewer
groups in a form refereekit does not recognize. When it comes back with
nothing, `or-fetch` does not write any `Official_Review` signed by a group
rather than a named profile into `theirs/`: it names those notes on stdout with
the forum id and leaves them for you to check on OpenReview. Everything else in
the discussion still arrives. `or-responses` reads all of `theirs/` as what
came back from others, so a review of yours stored there would be analyzed as
agreeing with itself.

**Venue LLM policies differ, and refereekit does not check or enforce them.**
Compliance is yours. Two current examples, worth knowing before you run
`or-draft`:

- **NeurIPS 2025** prohibits it: "You must keep everything relating to the
  review process confidential. Do not talk about or share submissions with
  anyone or any LLMs." Zero-retention API terms do not create an exception; the
  prohibition is on sharing at all, not on retention.
- **ICLR 2027** permits limited use but makes disclosure mandatory. If you use
  an LLM to generate or edit any portion of a review, you must report your
  original self-written assessment and your LLM interactions in an accompanying
  textbox, and the review form asks for it.

**Confidentiality.** Many venues restrict submissions to assigned reviewers. A
fetched submission is confidential manuscript text: keep it under the
git-ignored `work/` tree, never commit it, and send it only to a zero-retention
backend. `form.json` is venue configuration and carries no manuscript text.
`openreview.md`, `openreview.json`, and `response-analysis.txt` are derived from
the manuscript and are never committed, exactly like `report.txt`.

## What a PASS means

Verification is **quotation-scoped**. A `PASS` on a `page` or `quote` claim
means: *these exact words, normalized for whitespace and case, are on that
page.* Only text presented as a quotation is checked.

A citation carrying no quotation verifies as `FLAG`, not `PASS`. The page
exists, the wording was never checked. This is the common case: referee prose
paraphrases the manuscript, and a paraphrase cannot be substring-matched. It
is reported as unverified rather than treated as a failed citation.

`FLAG` is checked in that order deliberately, so it carries a guarantee: the
page is confirmed to be in the document. A citation to a page that is not
there is a `FAIL`, however little it quotes. That is what makes a `FLAG`
citation safe to keep in the claim pool and safe to cite in a draft, with only
its wording unverified.

A `PASS` on an `equation` or `figure` claim is weaker and structural: that ID
exists in the document. It says nothing about content.

Exit codes: `refereekit verify` returns 0 for PASS (verified), 1 for FAIL (contradicted), and 3 for FLAG (unverified). Calling scripts can distinguish confirmed claims from unverifiable ones.

**What verification cannot do:** it cannot tell you whether a mathematical
claim is true. "Is Eq. (25) an identity?" is not a substring question. That
stays human work: write a script and check it.

One more limit: a quotation shorter than four words is not verified. Quoted
spans under 12 characters are skipped as scare-quoting, and a span that
survives but carries fewer than four words verifies as `FLAG`. So a very
short quoted phrase is reported unverified rather than checked. Four words
is the floor at which a match stops being accidental.

## Extraction limits

- **Figures:** Reliably extracted from caption lines (handles "FIG." and "Figure" prefixes).
- **Equation numbers:** Best-effort extraction via right-margin geometry. Equation **bodies are not reconstructed** — PDF math rendering is lossy (bitmaps/glyphs, not LaTeX); source is unavailable post-compile. Noisy IDs remain possible on papers with complex multi-column layouts.
- **Sections:** Best-effort heading detection. Papers with non-standard heading styles (e.g., no caps/roman numerals in the text layer) may surface few or no sections.
- **Most reliable path:** Quote/page verification remains the robust anchor for review workflows.

## Test
    .venv/bin/pytest -v

## License

MIT — see [LICENSE](LICENSE).
