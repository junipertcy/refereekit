# OpenReview Support: Design

**Date:** 2026-08-06
**Status:** approved

## Goal

Review a paper assigned on OpenReview with the tooling refereekit already has:
fetch the assignment and its PDF, discover the venue's review form, draft the
form's prose fields from the verified claim pool, and summarize the authors'
responses. Output is written locally for copy-paste. refereekit never posts to
OpenReview.

## Motivation

Today `refereekit review paper.pdf --session ./work/paperA` needs a PDF already
on disk, and it produces a journal-shaped report plus an editor letter. Neither
half fits OpenReview. The paper lives behind an authenticated API, and the
deliverable is a structured form whose fields vary by venue: ICLR asks for
soundness, presentation, and contribution ratings; the OpenReview default form
asks only for title, review, rating, and confidence.

The mismatch in output shape is the larger of the two problems. A fetch is a
few API calls. Turning a report into the right set of named fields, without
hardcoding one venue's form, is the part that needs designing.

## Non-goals

- **Posting to OpenReview.** No `post_note_edit` call appears anywhere in this
  package. Posting is not one bug or one flag away; the code to do it does not
  exist. Nothing reaches the venue that the referee has not personally pasted.
- **Filling in ratings.** Verification is substring matching. It cannot
  distinguish a soundness of 3 from a 4. Numeric fields come back empty.
- **Enforcing venue LLM policy.** Explicitly out of scope by the referee's
  decision. See "Venue LLM policies" below for what is documented instead.
- **Posting comments in the discussion thread**, and **fetching the private
  reviewer-AC discussion.** Author responses are in scope; the private
  discussion phase is not.

## Architecture

The existing package has a shape worth preserving: `ingest` converts a PDF into
a `Document`, and every module downstream of it (`verify`, `drafts`, `render`)
is a pure function of local data. Nothing but `llm.py` touches a network.

OpenReview support keeps that property. One module makes network calls and
converts everything it receives into files under the session directory. Every
other new module is offline, and therefore testable without credentials.

New subpackage `refereekit/openreview/`, following the `refereekit/agent/`
precedent:

| Module | Responsibility | Imports |
|---|---|---|
| `client.py` | The only module that imports `openreview-py`. Assignments, PDF bytes, review-form invitation, forum replies. | `openreview-py` |
| `form.py` | Parse an invitation into a `ReviewForm`. Pure. | nothing |
| `fill.py` | Draft prose fields from the claim pool. Leave choice fields empty. | `drafts`, `llm` |
| `responses.py` | Summarize author responses against our own report. | `llm` |

### Naming

The subpackage is `refereekit.openreview` and the third-party package is
`openreview`. Inside `refereekit/openreview/client.py`, an absolute
`import openreview` resolves to the third-party package under Python 3's
absolute-import rule, so this works. It also reads as ambiguous. The module
therefore imports as:

```python
from openreview import api as openreview_api
```

No other module in the subpackage imports the third-party package at all.

### Dependency

`openreview-py` is an optional extra, like `anthropic`:

```toml
[project.optional-dependencies]
openreview = ["openreview-py>=1.40"]
```

`PyMuPDF` remains the only hard runtime dependency. `client.py` imports
`openreview_api` inside the functions that need it, not at module scope, so
`import refereekit.openreview.form` works without the extra installed. A missing
extra produces one actionable message, matching how `llm.py` handles a missing
`anthropic`.

## Data flow

```
or-fetch --venue V                      or-fetch --venue V --number 42
        |                                        |
   get_all_edges                          get_note + get_attachment
        |                                        |
   assignment list                         paper.pdf
   printed to stdout                            |
                                          ingest (existing, unchanged)
                                                |
                                          doc.json
                                                |
                                          get_invitation
                                                |
                                          form.py -> form.json
                                                |
                                          get_all_notes(forum, details)
                                                |
                                          theirs/<note-id>-<tcdate>.txt

review <session>/paper.pdf --session S
        |
   claims + verdict into state.json

or-draft --session S                    or-responses --session S
        |                                        |
   form.json + verified claim pool        theirs/ + ours/report.txt
        |                                        |
   fill.py (drafts.report per field)      responses.py
        |                                        |
   ours/openreview.md + .json             ours/response-analysis.txt
```

## Types

In `refereekit/openreview/form.py`:

```python
@dataclass
class Field:
    name: str            # 'summary', 'rating', 'soundness'
    type: str            # 'string', 'integer', 'string[]'
    order: int           # render order from the invitation
    description: str     # the venue's own instructions to the reviewer
    required: bool       # not param.optional
    enum: list           # [(value, description)]; empty for free text
    max_length: int | None
    widget: str          # 'textarea' | 'select' | 'radio' | 'text'

@dataclass
class ReviewForm:
    invitation_id: str
    fields: list[Field]          # sorted by order

    def prose_fields(self) -> list[Field]:
        """Free-text fields. refereekit drafts these."""

    def choice_fields(self) -> list[Field]:
        """Fields with an enum. Left empty for the referee."""
```

The `prose_fields` / `choice_fields` split is where the "drafted prose, blank
ratings" decision lives. `choice_fields` returns every field carrying a
non-empty enum, whatever its type. `prose_fields` returns every field whose
`type` starts with `string` and whose enum is empty. A field that is neither,
an enum-less integer or a `file`, appears in neither list and is reported as
"to fill in yourself" alongside the choice fields.

A field is classified by the presence of an enum, not by its name, so a venue
that calls its rating `overall_assessment` needs no change here.

`title` is a prose field by this rule and is drafted. That is correct: it is
free text and a one-line summary is the kind of thing a draft helps with.

## Review-form discovery

An OpenReview invitation is self-describing. The `Official_Review` invitation's
`edit.note.content` carries every field with its type, enum values, per-value
descriptions, order, and intended widget. Nesting, from the API v2 reference:

```json
{
  "id": "<venue>/Submission42/-/Official_Review",
  "edit": {
    "note": {
      "content": {
        "rating": {
          "value": { "param": {
            "type": "integer",
            "enum": [ {"value": 10, "description": "10: Top 5% ..."} ],
            "input": "select"
          } },
          "order": 3,
          "description": "..."
        }
      }
    }
  }
}
```

`form.py` walks `edit.note.content`, and for each field reads
`value.param` for `type`, `enum`, `optional`, `maxLength`, and `input`, and the
field level for `order` and `description`.

Three shapes must be handled, because real venue forms contain all of them:

1. **`enum` of objects:** `[{"value": 10, "description": "10: ..."}]`. The
   default form's rating and confidence. Parsed to `[(10, "10: ...")]`.
2. **`enum` of scalars:** `["Yes", "No"]`, with no descriptions. Parsed to
   `[("Yes", ""), ("No", "")]`.
3. **No `param` at all:** a field whose `value` is a literal constant rather
   than a specification. Skipped: it is not something a reviewer fills in.

Defaults when a key is absent: `order` sorts last, `description` is `""`,
`required` is True unless `param.optional` is true, `widget` is `"textarea"`
for a string with `maxLength` over 200 and `"text"` otherwise.

Unknown keys inside `param` are ignored rather than raising. A venue adding a
key must not break the fetch.

`form.json` is the serialized `ReviewForm`. It is written to the session so
`or-draft` needs no network, and so the form the draft was built against is
recoverable later.

## Commands

Three new subcommands in `cli.py`, following the existing `--session` pattern.

### `or-fetch`

```
refereekit or-fetch --venue ICLR.cc/2027/Conference --session ./work/iclr
```

With no `--number`, lists assignments and exits 0. Output is one line per
paper:

```
  42  Some Paper Title Here
  87  Another Paper Title
Fetch one with: --number <N>
```

Listing is a separate step from fetching because a referee needs to see what
they have before choosing, and because listing touches no manuscript content.

```
refereekit or-fetch --venue ICLR.cc/2027/Conference --number 42 --session ./work/iclr-42
```

With `--number`, this:

1. resolves the submission via `get_all_notes(invitation=f'{venue}/-/Submission', number=42)`
2. writes `paper.pdf` from `get_attachment(field_name='pdf', id=note.id)`
3. runs the existing `ingest` and `save_doc`, producing `doc.json`
4. writes `form.json` from `get_invitation(f'{venue}/Submission42/-/Official_Review')`
5. writes each reply into `theirs/`, excluding replies we signed ourselves
6. records `venue`, `number`, `forum` id, and `invitation_id` in session state

On step 5: a forum's replies include other reviewers' official reviews, author
comments, and our own review once posted. All of them are documents received
from others and belong in `theirs/`, with one exception: a reply whose
signatures are one of our own anonymous reviewer groups is ours, not theirs, and
storing it under `theirs/` would recreate exactly the confusion between our
draft and someone else's report that `ours/` and `theirs/` exist to prevent.
`or-fetch` resolves our anonymous group ids with
`get_groups(prefix=f'{venue}/Submission{N}/Reviewer_', signatory=profile_id)`
and skips any reply signed by one of them.

Each stored note's header records its invitation id, so `or-responses` can tell
an author comment from a co-reviewer's official review.

Steps 4 and 5 are best-effort. Before the review stage opens the invitation
does not exist, and before the rebuttal period there are no replies. Neither is
an error: the command prints what it skipped and still exits 0, because the PDF
and `doc.json` are the part the referee needs first.

### `or-draft`

```
refereekit or-draft --session ./work/iclr-42 [--style PATH] [--length summary=short]
```

Reads `form.json` and `doc.json`, drafts every prose field, writes
`ours/openreview.md` (for reading and pasting) and `ours/openreview.json` (the
field-name-to-value mapping, for a future poster or a diff).

The verified claim pool comes from a `review` pass over the fetched PDF in the
same session directory: `refereekit review <session>/paper.pdf --session
<session>`. `or-fetch` records the venue, the number and the forum, and the
review loop is what records claims and the verdict, so the OpenReview path is
three commands rather than two. `or-draft` on a session that has been fetched
but not reviewed exits 2 and names that command. It does not draft from an
empty pool: every field would be invented while the command reported success,
which is a worse failure than refusing.

Prints a summary:

```
openreview: 4 prose field(s) drafted, 2 flag(s)
  FLAG page (17): not in verified pool
to fill in yourself:
  rating       (1-10)   Overall assessment
  confidence   (1-5)    Reviewer confidence
```

Requires `REFEREEKIT_ZERO_RETENTION=1` or `REFEREEKIT_FAKE=1`, via the existing
`_backend()`. No new environment variables.

### `or-responses`

```
refereekit or-responses --session ./work/iclr-42
```

Reads `theirs/` and our own review, writes `ours/response-analysis.txt`. Our
review is `ours/openreview.md` when it exists, otherwise `ours/report.txt`; the
OpenReview-shaped draft is preferred because it is what the authors were
responding to. If neither exists, the analysis still runs and says so, since
reading the authors' responses before drafting is a legitimate order of work.

Errors with exit 2 if `theirs/` is empty: there is nothing to analyze, and an
empty output file would read as "the authors said nothing."

## Drafting the prose fields

`fill.py` reuses `drafts.report` rather than reimplementing prompt
construction, so the voice guide, the claim pool, the verified-versus-pointer
distinction, and `_verify_prose` anchor checking all apply unchanged.

One call per prose field, not one call for the whole form. Each field gets the
venue's own `description` as its instruction, because that description is the
venue telling the reviewer what belongs there, and it is better guidance than
anything refereekit could invent. Per-field calls also mean a field that fails
does not lose the others.

This requires threading one optional keyword argument through two existing
functions in `drafts.py`, both defaulting to `None` so current behavior is
byte-identical when it is absent:

```python
def build_prompt(pool, style, section_lengths, prior_notes=None,
                 field_instruction: str | None = None) -> str

def report(session, verdict, section_lengths, *, backend, style_path,
           memory=None, venue=None, field_instruction: str | None = None) -> Draft
```

`report` passes `field_instruction` straight to `build_prompt`, which inserts it
as a `=== THIS SECTION ===` block immediately before `=== SECTION LENGTHS ===`.
When it is `None` the block is omitted entirely, so the existing `draft` and
`editor` paths produce the same prompts they do today and their tests keep
passing unchanged. This is the same pattern `prior_notes` already uses.

`fill.py` calls `report` once per prose field with that field's `description`
as `field_instruction`, and with `section_lengths` narrowed to just that field:
`{f.name: lengths[f.name]}` when the referee gave a length for it, `{}`
otherwise. Passing the whole `--length` map to every field would tell each call
about lengths for sections it is not writing.

Flags aggregate: one `Draft` per field, concatenated into a single flag list,
deduplicated on `(kind, anchor, reason)` since the same unpooled anchor cited
in two fields is one problem, not two.

`--length` keys are field names, so `--length summary=short` controls the
`summary` field, consistent with the existing `--length intro=short`. A
`--length` key matching no field in the form is an error (exit 2) rather than a
silent no-op, because the likely cause is a typo or a form that differs from
the one the referee expected.

## Author responses

`responses.py` builds one prompt: our own report, the authors' responses, and
an instruction to report where the response addresses a point we raised, where
it does not, and where it makes a factual claim about the manuscript we should
re-check.

The output is a reading aid, not a verdict. It contains no ratings and no
recommendation. Its last line is a reminder that a claim about a revised
manuscript cannot be verified against `doc.json`, since `doc.json` holds the
version originally fetched.

Author responses are manuscript-adjacent text and go only to a zero-retention
backend, via the same `complete(..., manuscript_ok=True)` path.

## Provenance and revised rebuttals

`Session.put_theirs` is write-once and raises `ProvenanceError` on overwrite.
Author responses change during a discussion period, so re-fetching would crash
against that guard.

Received notes are therefore named `<note-id>-<tcdate>.txt`. A revised response
has a new `tcdate` and so becomes a new file; both versions are kept and the
change is visible. Re-fetching an unchanged note produces the same filename,
which `put_theirs` would reject, so `or-fetch` skips a file that already
exists and reports it as unchanged.

This strengthens write-once rather than working around it. `theirs/` is the
directory whose absence previously caused a co-referee's report to be confused
with our own draft.

Each file carries a two-line header before the note body, so a file read in
isolation says what it is:

```
# openreview note <id> by <signature> at <tcdate-as-iso>
# invitation: <invitation-id>
```

`tcdate` is OpenReview's own creation timestamp in epoch milliseconds. It is
data from the API, not a local clock reading, so it is deterministic across
re-fetches.

## Credentials

Read from `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD`. No flags: a password
in a flag lands in shell history and in the process table. Credentials are
never written to the session directory, never logged, and never included in an
error message.

The client is constructed once per command invocation:

```python
openreview_api.OpenReviewClient(
    baseurl="https://api2.openreview.net",
    username=..., password=...,
)
```

API v2 only. Every current venue has migrated. A v1-only legacy venue is out of
scope and produces the same "not found" path as a mistyped venue id.

`--baseurl` is accepted so the API sandbox at `https://devapi2.openreview.net`
can be used for a live smoke test without touching production.

## API calls used

All confirmed against `openreview/api/client.py` on master, not against the
readthedocs page, which documents the v1 client and disagrees with v2 on
argument order.

| Purpose | Call |
|---|---|
| Own profile id | `get_profile()` |
| Assignments | `get_all_edges(invitation=f'{venue}/Reviewers/-/Assignment', tail=profile_id)` |
| Submission | `get_all_notes(invitation=f'{venue}/-/Submission', number=N)` |
| PDF | `get_attachment(field_name='pdf', id=note.id)` |
| Review form | `get_invitation(f'{venue}/Submission{N}/-/Official_Review')` |
| Replies | `get_all_notes(forum=forum_id, details='replies')` |
| Our own anon groups | `get_groups(prefix=f'{venue}/Submission{N}/Reviewer_', signatory=profile_id)` |

**`get_attachment` takes `field_name` first.** The v2 signature is
`get_attachment(self, field_name, id=None, ids=None, ...)`, the reverse of the
widely-copied v1 example `get_attachment(note.id, 'pdf')`. Calling it
positionally on a v2 client passes the note id as the field name and fails
with a confusing 404. Both arguments are passed by keyword.

`get_all_edges` on the v2 client takes no `limit` or `offset`; it streams. A
reviewer's assignment count is tens of papers, so no pagination is needed.

`get_all_notes` takes `number` directly, so the submission lookup does not
fetch every paper in the venue to filter locally.

Assignment edges give `edge.head` (the submission id) but not the paper number
or title, so `or-fetch` with no `--number` resolves each head with `get_note`
to print a useful list.

## Error handling

Follows the established pattern: catch specific exceptions, print
`error: {e}` to stderr, return 2.

| Condition | Message |
|---|---|
| `openreview-py` not installed | `openreview support requires: pip install -e ".[openreview]"` |
| Credentials unset | `set OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD` |
| Bad credentials | `openreview login failed for <username>` (no password echo) |
| Venue not found | `no venue <id>; check the venue id, e.g. ICLR.cc/2027/Conference` |
| No assignments | `no assignments for <profile> at <venue>` (exit 0, not an error) |
| Paper not assigned to you | `submission <N> is not assigned to you at <venue>` |
| Submission has no PDF | `submission <N> has no pdf attachment` |
| Review stage not open | warning, not an error: `no review form yet at <invitation>; skipping form.json` |
| No replies yet | warning: `no replies yet; theirs/ left empty` |
| `or-draft` with no `form.json` | `no form.json; run or-fetch --number first` |
| `or-draft` with no claim pool | `no verified claims in this session; run refereekit review <session>/paper.pdf --session <session> first` |
| `or-responses` with empty `theirs/` | `no received notes in theirs/; nothing to analyze` |

`openreview.OpenReviewException` is caught at the `client.py` boundary and
re-raised as a `refereekit`-local error type, so `cli.py` does not import the
third-party exception and the CLI keeps working with the extra uninstalled.

## Testing

Everything must run offline, and no confidential submission may be committed.
The repo's standing rule holds: the only committable PDF is the existing
fixture under `tests/fixtures/`.

**`form.py`** gets pure tests against checked-in fixture JSON. Two fixtures:
OpenReview's published default review form, and a synthetic ICLR-shaped form
with `summary`, `strengths`, `weaknesses`, `soundness`, `presentation`,
`contribution`, `rating`, `confidence`. Both are public venue configuration,
not manuscript text, so both are safe to commit. Cases: the three enum shapes,
absent `order`, absent `description`, `param.optional`, an unknown `param` key,
and `edit.note.content` missing entirely.

**`client.py`** gets a `FakeORClient`, mirroring `FakeBackend` in `llm.py`:
canned assignments, the fixture PDF's bytes for `get_attachment`, a fixture
invitation, and canned replies. This lets the whole pipeline run in tests with
no network and no credentials. `FakeORClient` records the keyword arguments it
was called with, so a test asserts `get_attachment` was called with
`field_name='pdf'`, pinning the argument-order finding above.

**`fill.py`** tests ingest `tests/fixtures/real_paper.pdf` and run with
`FakeBackend`, following `test_agent_qa.py`. The load-bearing assertion: every
`choice_field` is absent from or empty in `openreview.json`. That is the
non-negotiable behavior, so it gets a test that fails loudly if drafting ever
starts filling ratings.

**Provenance** gets a test that fetching twice does not raise, that a note with
a new `tcdate` produces a second file, and that both files remain. Also that a
reply signed by one of our own anonymous reviewer groups does not land in
`theirs/`, while a co-reviewer's review and an author comment both do.

**CLI** tests cover each exit code and each error message above.

## Venue LLM policies

refereekit does not check or enforce venue policy. That is a deliberate
decision by the referee, and the code contains no gate. The README will state
the following as prose, and state plainly that compliance is the referee's
responsibility:

- **NeurIPS 2025** prohibits it outright: "You must keep everything relating to
  the review process confidential. Do not talk about or share submissions with
  anyone or any LLMs." Zero-retention API terms do not create an exception,
  because the prohibition is on sharing at all, not on retention.
- **ICLR 2027** permits limited use but makes disclosure mandatory: if an LLM
  is used to generate or edit any portion of a review, the reviewer must report
  their original self-written assessment and their LLM interactions in an
  accompanying textbox, and the form solicits this.

Both quotations are from the venues' own published policy pages, verified
during design research.

## Confidentiality

The existing rules apply unchanged, and one is worth restating because
OpenReview makes it easy to get wrong. Many venues restrict submissions to
assigned reviewers only. A fetched submission is confidential manuscript text:
it belongs under the git-ignored `work/` tree, it is never committed, and it
goes only to a zero-retention backend.

`form.json` is venue configuration and carries no manuscript text.
`response-analysis.txt` and `openreview.md` are derived from the manuscript and
are never committed, exactly like `report.txt` today.
