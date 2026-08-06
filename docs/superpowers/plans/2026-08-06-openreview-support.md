# OpenReview Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch a reviewer's OpenReview assignment and its PDF, discover the venue's review form from its invitation, draft the form's prose fields from the verified claim pool, and summarize the authors' responses.

**Architecture:** One module (`client.py`) makes every network call and converts what it receives into files under the session directory. Every other new module is a pure function of local data, so the whole pipeline is testable with no credentials and no network. This preserves the property `ingest` already has.

**Tech Stack:** Python 3.11+, `openreview-py` (new optional extra), PyMuPDF (existing), pytest.

**Spec:** `docs/superpowers/specs/2026-08-06-openreview-support-design.md`

## Global Constraints

- **Read-only.** No `post_note_edit` call may appear anywhere in this package. Posting is out of scope by design, not by omission.
- **Numeric and enum fields are never filled.** Verification is substring matching; it cannot tell a soundness of 3 from a 4. `choice_fields()` come back empty for the referee.
- **`get_attachment` takes `field_name` FIRST** on the v2 client: `get_attachment(self, field_name, id=None, ids=None, group_id=None, invitation_id=None)`. This is the reverse of the widely-copied v1 example `get_attachment(note.id, 'pdf')`. Always pass both by keyword. Confirmed against `openreview/api/client.py` on master; readthedocs documents v1 and disagrees.
- **`get_all_edges` on v2 takes no `limit` or `offset`.** It streams: `get_all_edges(self, id=None, invitation=None, head=None, tail=None, label=None, trash=None, select=None, domain=None)`.
- **API v2 only.** `baseurl="https://api2.openreview.net"`.
- **Credentials come from `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD` only.** Never a CLI flag (shell history, process table). Never written to the session, logged, or included in an error message.
- **`openreview-py` is an optional extra.** `PyMuPDF>=1.24` remains the only hard runtime dependency. Import `openreview` inside functions, never at module scope, and only in `client.py`.
- **Inside `refereekit/openreview/client.py`, import the third-party package as `from openreview import api as openreview_api`.** No other module in the subpackage imports it.
- **`refereekit.openreview.client.ORError` is the only exception type `cli.py` sees.** `cli.py` must not import any `openreview` exception, so the CLI keeps working with the extra uninstalled.
- **Error handling follows the existing CLI pattern:** catch specific exceptions, `print(f"error: {e}", file=sys.stderr)`, `return 2`.
- **No manuscript text in any committed file.** The only committable PDF is the existing `tests/fixtures/real_paper.pdf`. Form fixtures are public venue configuration and are safe to commit.
- **No em-dashes, en-dashes, or `---` as punctuation** in code, comments, docstrings, or docs.
- **`work/` is git-ignored.** Never `git add` anything under it.

---

## File Structure

| File | Responsibility |
|---|---|
| `refereekit/openreview/__init__.py` | Re-export the public surface, following `refereekit/agent/__init__.py`. |
| `refereekit/openreview/form.py` | Parse an invitation into a `ReviewForm`. Pure. No network, no LLM. |
| `refereekit/openreview/client.py` | Every network call. Plus `store_replies`, the one pure function there, which owns `theirs/` naming. |
| `refereekit/openreview/fill.py` | Draft prose fields via `drafts.report`. Render markdown and JSON. |
| `refereekit/openreview/responses.py` | Summarize author responses against our own review. |
| `refereekit/drafts.py` | Modified: one optional `field_instruction` keyword threaded through `build_prompt` and `report`. |
| `refereekit/cli.py` | Modified: `or-fetch`, `or-draft`, `or-responses`. |
| `pyproject.toml` | Modified: `openreview` optional extra. |
| `README.md` | Modified: usage plus the venue LLM policies. |
| `tests/fixtures/openreview_default_form.json` | OpenReview's published default review form, in invitation shape. |
| `tests/fixtures/openreview_iclr_form.json` | Synthetic ICLR-shaped form: summary, strengths, weaknesses, soundness, presentation, contribution, rating, confidence. |
| `tests/openreview_fakes.py` | `FakeORClient`, mirroring `FakeBackend` in `llm.py`. Records call kwargs. |
| `tests/test_or_form.py` | Form parsing, including the three enum shapes and every absent-key default. |
| `tests/test_or_client.py` | Fetch functions and `theirs/` provenance, against `FakeORClient`. |
| `tests/test_or_fill.py` | Prose drafting, and the load-bearing assertion that choice fields stay empty. |
| `tests/test_or_responses.py` | Prompt shape and the empty-`theirs/` error. |
| `tests/test_cli_openreview.py` | Each new subcommand, each exit code. |

---

## Task 1: Review-form parsing

The foundation. An OpenReview invitation is self-describing, so this module turns one into a `ReviewForm` and every venue's form works without venue-specific code. Pure, so it needs no credentials to test.

**Files:**
- Create: `refereekit/openreview/__init__.py`
- Create: `refereekit/openreview/form.py`
- Create: `tests/fixtures/openreview_default_form.json`
- Create: `tests/fixtures/openreview_iclr_form.json`
- Modify: `pyproject.toml`
- Test: `tests/test_or_form.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Field(name: str, type: str, order: int, description: str, required: bool, enum: list, max_length: int | None, widget: str)` dataclass
  - `ReviewForm(invitation_id: str, fields: list)` dataclass with `prose_fields() -> list`, `choice_fields() -> list`, `other_fields() -> list`
  - `parse_form(invitation: dict) -> ReviewForm`
  - `to_json(form: ReviewForm) -> str`, `from_json(s: str) -> ReviewForm`

- [ ] **Step 1: Add the optional extra to `pyproject.toml`**

In the `[project.optional-dependencies]` block, after the `llm` line:

```toml
[project.optional-dependencies]
dev = ["pytest>=8"]
llm = ["anthropic>=0.40"]
openreview = ["openreview-py>=1.40"]
```

- [ ] **Step 2: Create the two form fixtures**

`tests/fixtures/openreview_default_form.json`. This is OpenReview's published default review form, wrapped in the invitation shape `parse_form` receives. Note `rating` uses an enum of objects and `confidence` uses `"input": "radio"`.

```json
{
  "id": "Test.cc/2027/Conference/Submission42/-/Official_Review",
  "edit": {
    "note": {
      "content": {
        "title": {
          "value": { "param": { "type": "string", "regex": ".{0,500}" } },
          "order": 1,
          "description": "Brief summary of your review."
        },
        "review": {
          "value": { "param": {
            "type": "string", "minLength": 1, "maxLength": 20000,
            "input": "textarea", "markdown": true
          } },
          "order": 2,
          "description": "Please provide an evaluation of the quality, clarity, originality and significance of this work."
        },
        "rating": {
          "value": { "param": {
            "type": "integer",
            "enum": [
              { "value": 10, "description": "10: Top 5% of accepted papers, seminal paper" },
              { "value": 8, "description": "8: Top 50% of accepted papers, clear accept" },
              { "value": 5, "description": "5: Marginally below acceptance threshold" },
              { "value": 1, "description": "1: Trivial or wrong" }
            ],
            "input": "select"
          } },
          "order": 3
        },
        "confidence": {
          "value": { "param": {
            "type": "integer",
            "enum": [
              { "value": 5, "description": "5: The reviewer is absolutely certain" },
              { "value": 3, "description": "3: The reviewer is fairly confident" },
              { "value": 1, "description": "1: The reviewer's evaluation is an educated guess" }
            ],
            "input": "radio"
          } },
          "order": 4
        }
      }
    }
  }
}
```

`tests/fixtures/openreview_iclr_form.json`. Synthetic, ICLR-shaped. It deliberately exercises every edge case: `venueid` is a literal constant with no `param` (must be skipped), `flag_for_ethics_review` is an enum of bare scalars, `confidential_comment` is optional, `supplementary` is a `file`, `code_of_conduct` has no `order` and no `description`, and `presentation` carries an unknown `param` key.

```json
{
  "id": "ICLR.cc/2027/Conference/Submission42/-/Official_Review",
  "edit": {
    "note": {
      "content": {
        "venueid": { "value": "ICLR.cc/2027/Conference" },
        "summary": {
          "value": { "param": { "type": "string", "maxLength": 5000, "markdown": true } },
          "order": 1,
          "description": "Summarize the paper in your own words."
        },
        "strengths": {
          "value": { "param": { "type": "string", "maxLength": 5000 } },
          "order": 2,
          "description": "List the strengths of the submission."
        },
        "weaknesses": {
          "value": { "param": { "type": "string", "maxLength": 5000 } },
          "order": 3,
          "description": "List the weaknesses of the submission."
        },
        "soundness": {
          "value": { "param": {
            "type": "integer",
            "enum": [
              { "value": 4, "description": "4: excellent" },
              { "value": 1, "description": "1: poor" }
            ],
            "input": "radio"
          } },
          "order": 4,
          "description": "Assess the soundness of the technical claims."
        },
        "presentation": {
          "value": { "param": {
            "type": "integer",
            "enum": [
              { "value": 4, "description": "4: excellent" },
              { "value": 1, "description": "1: poor" }
            ],
            "input": "radio",
            "someFutureKey": "ignore me"
          } },
          "order": 5
        },
        "contribution": {
          "value": { "param": {
            "type": "integer",
            "enum": [
              { "value": 4, "description": "4: excellent" },
              { "value": 1, "description": "1: poor" }
            ],
            "input": "radio"
          } },
          "order": 6
        },
        "rating": {
          "value": { "param": {
            "type": "integer",
            "enum": [
              { "value": 8, "description": "8: accept, good paper" },
              { "value": 3, "description": "3: reject, not good enough" }
            ],
            "input": "select"
          } },
          "order": 7,
          "description": "Overall assessment."
        },
        "confidence": {
          "value": { "param": {
            "type": "integer",
            "enum": [
              { "value": 5, "description": "5: absolutely certain" },
              { "value": 1, "description": "1: educated guess" }
            ],
            "input": "radio"
          } },
          "order": 8
        },
        "flag_for_ethics_review": {
          "value": { "param": {
            "type": "string[]",
            "enum": ["No ethics review needed.", "Yes, Privacy and security"],
            "input": "checkbox"
          } },
          "order": 9,
          "description": "Does this submission need an ethics review?"
        },
        "confidential_comment": {
          "value": { "param": { "type": "string", "maxLength": 5000, "optional": true } },
          "order": 10,
          "description": "Comments visible to the area chairs only."
        },
        "supplementary": {
          "value": { "param": { "type": "file", "extensions": ["pdf"], "optional": true } },
          "order": 11,
          "description": "Optional attachment."
        },
        "code_of_conduct": {
          "value": { "param": { "type": "string", "enum": ["I agree"], "input": "checkbox" } }
        }
      }
    }
  }
}
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_or_form.py`:

```python
import json
from pathlib import Path
from refereekit.openreview import form as orform

FIXTURES = Path("tests/fixtures")


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def _default():
    return orform.parse_form(_load("openreview_default_form.json"))


def _iclr():
    return orform.parse_form(_load("openreview_iclr_form.json"))


def test_default_form_field_names_in_order():
    f = _default()
    assert [x.name for x in f.fields] == ["title", "review", "rating", "confidence"]
    assert f.invitation_id.endswith("Submission42/-/Official_Review")


def test_prose_and_choice_split_on_the_default_form():
    """The split is the whole 'drafted prose, blank ratings' decision."""
    f = _default()
    assert [x.name for x in f.prose_fields()] == ["title", "review"]
    assert [x.name for x in f.choice_fields()] == ["rating", "confidence"]


def test_enum_of_objects_keeps_value_and_description():
    rating = next(x for x in _default().fields if x.name == "rating")
    assert rating.enum[0] == (10, "10: Top 5% of accepted papers, seminal paper")
    assert rating.type == "integer"
    assert rating.widget == "select"


def test_enum_of_bare_scalars_gets_empty_descriptions():
    """Real venues use both enum shapes. A bare list has no descriptions."""
    ethics = next(x for x in _iclr().fields if x.name == "flag_for_ethics_review")
    assert ethics.enum == [("No ethics review needed.", ""),
                           ("Yes, Privacy and security", "")]


def test_literal_constant_field_is_skipped():
    """venueid has a literal value and no param: it is not something a
    reviewer fills in, so it is not a form field."""
    assert "venueid" not in [x.name for x in _iclr().fields]


def test_unknown_param_key_does_not_raise():
    """A venue adding a key must not break the fetch."""
    pres = next(x for x in _iclr().fields if x.name == "presentation")
    assert pres.widget == "radio"


def test_absent_order_sorts_last_and_absent_description_is_empty():
    f = _iclr()
    assert f.fields[-1].name == "code_of_conduct"
    assert f.fields[-1].description == ""


def test_optional_param_makes_the_field_not_required():
    f = _iclr()
    assert next(x for x in f.fields if x.name == "confidential_comment").required is False
    assert next(x for x in f.fields if x.name == "summary").required is True


def test_iclr_prose_fields_are_the_narrative_ones():
    assert [x.name for x in _iclr().prose_fields()] == [
        "summary", "strengths", "weaknesses", "confidential_comment"]


def test_iclr_choice_fields_include_every_rating():
    names = [x.name for x in _iclr().choice_fields()]
    for expected in ("soundness", "presentation", "contribution", "rating",
                     "confidence", "flag_for_ethics_review", "code_of_conduct"):
        assert expected in names


def test_file_field_is_neither_prose_nor_choice():
    """An enum-less non-string is nothing we can draft, so it is reported to
    the referee rather than silently dropped."""
    f = _iclr()
    assert "supplementary" not in [x.name for x in f.prose_fields()]
    assert "supplementary" not in [x.name for x in f.choice_fields()]
    assert "supplementary" in [x.name for x in f.other_fields()]


def test_every_field_lands_in_exactly_one_bucket():
    f = _iclr()
    buckets = f.prose_fields() + f.choice_fields() + f.other_fields()
    assert sorted(x.name for x in buckets) == sorted(x.name for x in f.fields)


def test_missing_content_yields_an_empty_form():
    f = orform.parse_form({"id": "x", "edit": {}})
    assert f.fields == [] and f.invitation_id == "x"


def test_json_round_trip_preserves_the_split():
    before = _iclr()
    after = orform.from_json(orform.to_json(before))
    assert [x.name for x in after.prose_fields()] == [x.name for x in before.prose_fields()]
    assert after.fields[2] == before.fields[2]
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_or_form.py -v`
Expected: FAIL, collection error `ModuleNotFoundError: No module named 'refereekit.openreview'`

- [ ] **Step 5: Create the subpackage `__init__.py`**

`refereekit/openreview/__init__.py`. Only `form` is re-exported for now; later tasks extend this.

```python
from .form import Field, ReviewForm, parse_form
```

- [ ] **Step 6: Implement `form.py`**

Create `refereekit/openreview/form.py`:

```python
"""Parse an OpenReview review-form invitation into a ReviewForm.

Pure: no network, no LLM. An OpenReview invitation is self-describing, so a
venue's form is discovered at runtime instead of hardcoded. That is what lets
ICLR's soundness/presentation/contribution and the default form's bare
rating/confidence both work with no venue-specific code.

A field is classified by whether the invitation gives it an enum, not by its
name, so a venue calling its rating 'overall_assessment' needs no change here.
"""
import json
from dataclasses import dataclass, asdict

# A field with no 'order' sorts after every field that has one. Real forms
# number from 1, so any large constant does; this one is readable in a diff.
_ORDER_LAST = 10 ** 6


@dataclass
class Field:
    name: str
    type: str             # 'string', 'integer', 'string[]', 'file'
    order: int
    description: str      # the venue's own instruction to the reviewer
    required: bool
    enum: list            # [(value, description)]; empty for free text
    max_length: int | None
    widget: str           # 'textarea' | 'select' | 'radio' | 'text' | 'checkbox'


@dataclass
class ReviewForm:
    invitation_id: str
    fields: list          # sorted by order

    def prose_fields(self) -> list:
        """Free text. refereekit drafts these."""
        return [f for f in self.fields
                if f.type.startswith("string") and not f.enum]

    def choice_fields(self) -> list:
        """Anything with an enum. Left empty for the referee: verification is
        substring matching and cannot justify one rating over another."""
        return [f for f in self.fields if f.enum]

    def other_fields(self) -> list:
        """Neither: an enum-less integer, a file upload. The referee fills
        these too, so they are reported rather than dropped."""
        claimed = {f.name for f in self.prose_fields()}
        claimed |= {f.name for f in self.choice_fields()}
        return [f for f in self.fields if f.name not in claimed]


def _parse_enum(raw) -> list:
    """Two shapes appear in real forms: a list of {value, description} objects,
    and a bare list of scalars with no descriptions."""
    out = []
    for item in raw or []:
        if isinstance(item, dict):
            out.append((item.get("value"), item.get("description", "")))
        else:
            out.append((item, ""))
    return out


def _widget(param: dict, ftype: str, max_length) -> str:
    """The invitation's own 'input' when it gives one. Otherwise a long string
    is a textarea and everything else is a single line."""
    if param.get("input"):
        return param["input"]
    if ftype.startswith("string") and max_length is not None and max_length > 200:
        return "textarea"
    return "text"


def parse_form(invitation: dict) -> ReviewForm:
    """Read edit.note.content, one Field per entry a reviewer fills in.

    Unknown keys inside param are ignored rather than raising: a venue adding
    a key must not break the fetch.
    """
    edit = invitation.get("edit") or {}
    content = ((edit.get("note") or {}).get("content")) or {}
    fields = []
    for name, spec in content.items():
        if not isinstance(spec, dict):
            continue
        value = spec.get("value")
        if not isinstance(value, dict) or not isinstance(value.get("param"), dict):
            # A literal constant, not a specification. Not a reviewer input.
            continue
        param = value["param"]
        ftype = param.get("type", "string")
        max_length = param.get("maxLength")
        fields.append(Field(
            name=name,
            type=ftype,
            order=spec.get("order", _ORDER_LAST),
            description=spec.get("description", ""),
            required=not param.get("optional", False),
            enum=_parse_enum(param.get("enum")),
            max_length=max_length,
            widget=_widget(param, ftype, max_length),
        ))
    fields.sort(key=lambda f: (f.order, f.name))
    return ReviewForm(invitation_id=invitation.get("id", ""), fields=fields)


def to_json(form: ReviewForm) -> str:
    """Serialized to the session so or-draft needs no network, and so the form
    a draft was built against stays recoverable."""
    return json.dumps({
        "invitation_id": form.invitation_id,
        "fields": [{**asdict(f), "enum": [list(e) for e in f.enum]}
                   for f in form.fields],
    }, indent=2)


def from_json(s: str) -> ReviewForm:
    o = json.loads(s)
    return ReviewForm(
        invitation_id=o["invitation_id"],
        fields=[Field(**{**d, "enum": [tuple(e) for e in d["enum"]]})
                for d in o["fields"]],
    )
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_or_form.py -v`
Expected: PASS, 14 tests.

- [ ] **Step 8: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: 164 passing (150 existing plus 14 new).

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml refereekit/openreview/ tests/test_or_form.py \
        tests/fixtures/openreview_default_form.json \
        tests/fixtures/openreview_iclr_form.json
git commit -m "feat: parse an openreview review-form invitation

An invitation is self-describing, so the venue's form is discovered at
runtime rather than hardcoded. Fields are classified by whether the
invitation gives them an enum, not by name, so a venue calling its rating
overall_assessment needs no new code.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Per-field prompt instruction in `drafts.py`

`fill.py` will call `drafts.report` once per prose field, and each call needs the venue's own instruction for that field. This threads one optional keyword through two existing functions. Both default to `None`, so current behavior is byte-identical when absent and every existing test keeps passing unchanged. This is the same pattern `prior_notes` already uses.

**Files:**
- Modify: `refereekit/drafts.py:62-87` (`build_prompt`), `refereekit/drafts.py:105-113` (`report`)
- Test: `tests/test_drafts_field_instruction.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `drafts.build_prompt(pool, style, section_lengths, prior_notes=None, field_instruction: str | None = None) -> str`
  - `drafts.report(session, verdict, section_lengths, *, backend, style_path, memory=None, venue=None, field_instruction: str | None = None) -> Draft`

- [ ] **Step 1: Write the failing test**

Create `tests/test_drafts_field_instruction.py`:

```python
from refereekit import drafts
from refereekit.llm import FakeBackend
from refereekit.session import Session
from refereekit.ingest import ingest

POOL = {"claims": [], "verdict": {"recommend": "minor"}}


def test_field_instruction_appears_in_the_prompt():
    p = drafts.build_prompt(POOL, "voice", {}, None,
                            field_instruction="Write the 'summary' field.")
    assert "=== THIS SECTION ===" in p
    assert "Write the 'summary' field." in p


def test_field_instruction_precedes_section_lengths():
    """Order matters for readability of the assembled prompt."""
    p = drafts.build_prompt(POOL, "voice", {}, None, field_instruction="X")
    assert p.index("=== THIS SECTION ===") < p.index("=== SECTION LENGTHS ===")


def test_omitting_field_instruction_changes_nothing():
    """The existing draft and editor paths must produce identical prompts."""
    without = drafts.build_prompt(POOL, "voice", {"intro": "short"})
    explicit_none = drafts.build_prompt(POOL, "voice", {"intro": "short"},
                                        None, None)
    assert without == explicit_none
    assert "THIS SECTION" not in without


def test_report_passes_field_instruction_through(tmp_path, real_pdf_path):
    """report() is what fill.py calls, so the keyword has to reach the prompt
    from there, not just from build_prompt."""
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(real_pdf_path))
    seen = []
    backend = FakeBackend(lambda prompt: seen.append(prompt) or "drafted")
    d = drafts.report(s, {}, {}, backend=backend, style_path="style/STYLE.md",
                      field_instruction="Write the 'weaknesses' field.")
    assert d.text == "drafted"
    assert "Write the 'weaknesses' field." in seen[0]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_drafts_field_instruction.py -v`
Expected: FAIL with `TypeError: build_prompt() takes 3 positional arguments but 5 were given` (or `unexpected keyword argument 'field_instruction'`)

- [ ] **Step 3: Add the parameter to `build_prompt`**

In `refereekit/drafts.py`, change the signature on line 62 and add the block. The full replacement for the function's signature and the two lines that build the return value:

```python
def build_prompt(pool: dict, style: str, section_lengths: dict, prior_notes: list[str] = None,
                 field_instruction: str | None = None) -> str:
    lengths = ", ".join(f"{k}={v}" for k, v in section_lengths.items()) or "default"

    prior_section = ""
    if prior_notes:
        prior_section = (
            "=== PRIOR NOTES (your style/verdict patterns for this venue) ===\n" +
            "\n".join(f"- {n}" for n in prior_notes) + "\n\n"
        )

    # One named field of a structured review form, when that is what we are
    # writing. The instruction is the venue's own description of the field:
    # better guidance than anything we could invent.
    field_section = ""
    if field_instruction:
        field_section = f"=== THIS SECTION ===\n{field_instruction}\n\n"

    return (
        "Write a referee report in the voice described below.\n\n"
        f"=== VOICE GUIDE ===\n{style}\n\n"
        f"{prior_section}"
        f"=== VERDICT ===\n{pool['verdict']}\n\n"
        f"{_claim_lines(pool)}\n\n"
        f"{field_section}"
        f"=== SECTION LENGTHS ===\n{lengths}\n\n"
        "Cite page/equation anchors only if they appear above. Quote the "
        "manuscript's words only from VERIFIED QUOTATIONS; for unverified "
        "pointers, cite the page without quoting.\n\n"
        "=== CITATION FORMAT ===\n"
        "When citing pages and equations, use ONLY these forms:\n"
        "- Page citations: 'p. N' (e.g., 'p. 16')\n"
        "- Equation citations: 'Eq. (N)' with parentheses (e.g., 'Eq. (3)')\n"
        "Use no other citation style or format."
    )
```

- [ ] **Step 4: Add the parameter to `report`**

Replace `report` (currently `refereekit/drafts.py:105-113`):

```python
def report(session, verdict: dict, section_lengths: dict, *, backend, style_path,
           memory=None, venue=None, field_instruction: str | None = None) -> Draft:
    pool = build_pool(session)
    prior_notes = None
    if memory is not None and venue is not None:
        notes = memory.recall(venue)
        prior_notes = [n.text for n in notes]
    prompt = build_prompt(pool, load_style(style_path), section_lengths, prior_notes,
                          field_instruction)
    prose = complete(prompt, backend=backend, manuscript_ok=True)
    return _verify_prose(prose, pool, session.load_doc())
```

- [ ] **Step 5: Run the new test to verify it passes**

Run: `.venv/bin/pytest tests/test_drafts_field_instruction.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 6: Run the whole suite to confirm nothing regressed**

Run: `.venv/bin/pytest -q`
Expected: all passing. The existing `tests/test_drafts_report.py`, `tests/test_drafts_editor.py`, and `tests/test_agent_run_review.py` must pass untouched: that is the point of the `None` default.

- [ ] **Step 7: Commit**

```bash
git add refereekit/drafts.py tests/test_drafts_field_instruction.py
git commit -m "feat: optional per-field instruction in the report prompt

A structured review form is written one named field at a time, and the
venue's own description of a field is better guidance than anything we
could invent. Defaults to None so the existing draft and editor paths
produce identical prompts.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: The network boundary

Every OpenReview call lives here. Each function takes an already-constructed client, so tests inject `FakeORClient` and no test needs credentials or a network.

**Files:**
- Create: `refereekit/openreview/client.py`
- Create: `tests/openreview_fakes.py`
- Modify: `refereekit/openreview/__init__.py`
- Test: `tests/test_or_client.py`

**Interfaces:**
- Consumes: `form.parse_form(invitation: dict) -> ReviewForm` from Task 1.
- Produces:
  - `ORError(RuntimeError)`
  - `Assignment(number: int, forum: str, title: str)` dataclass
  - `BASEURL = "https://api2.openreview.net"`
  - `make_client(baseurl: str = BASEURL)`
  - `profile_id(client) -> str`
  - `list_assignments(client, venue: str) -> list[Assignment]`
  - `fetch_submission(client, venue: str, number: int) -> tuple[bytes, str]` returning `(pdf_bytes, forum_id)`
  - `fetch_form(client, venue: str, number: int) -> ReviewForm | None`
  - `our_group_ids(client, venue: str, number: int) -> set[str]`
  - `fetch_replies(client, forum: str) -> list[dict]`
  - `store_replies(session, replies: list[dict], skip_signatures: set[str]) -> tuple[list, list]` returning `(written_names, skipped_names)`

- [ ] **Step 1: Write the fake client**

Create `tests/openreview_fakes.py`. It stands in for `openreview.api.OpenReviewClient`, mirroring how `FakeBackend` in `llm.py` stands in for `AnthropicBackend`. It records every call's keyword arguments so a test can pin `get_attachment`'s argument order.

```python
"""A stand-in for openreview.api.OpenReviewClient.

Mirrors FakeBackend in refereekit/llm.py: the real client is never unit-tested
against the network, so the fake is what the pipeline runs against. It records
the keyword arguments of every call, which is how a test pins get_attachment's
argument order.
"""
from dataclasses import dataclass, field


@dataclass
class FakeNote:
    id: str
    number: int = 0
    content: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)


@dataclass
class FakeEdge:
    head: str
    tail: str = "~Test_User1"


@dataclass
class FakeGroup:
    id: str


@dataclass
class FakeProfile:
    id: str


class Boom(Exception):
    """Stands in for openreview.OpenReviewException, which client.py must
    translate at its boundary rather than let escape."""


class FakeORClient:
    def __init__(self, *, profile="~Test_User1", edges=None, notes=None,
                 invitation=None, groups=None, pdf=b"%PDF-1.4 fake",
                 replies=None, raise_on=()):
        # The default pdf is not a real PDF: it exercises byte passthrough only.
        # A test that ingests what it fetches must pass real_pdf_path.read_bytes().
        self.profile = profile
        self._edges = list(edges or [])
        self._notes = dict(notes or {})        # number -> FakeNote
        self._invitation = invitation
        self._groups = list(groups or [])
        self._pdf = pdf
        self._replies = list(replies or [])
        self._raise_on = set(raise_on)
        self.calls = []                        # [(method, kwargs)]

    def _log(self, method, **kw):
        self.calls.append((method, kw))
        if method in self._raise_on:
            raise Boom(f"fake failure in {method}")

    def kwargs_for(self, method):
        return [kw for name, kw in self.calls if name == method]

    def get_profile(self):
        self._log("get_profile")
        return FakeProfile(id=self.profile)

    def get_all_edges(self, **kw):
        self._log("get_all_edges", **kw)
        return list(self._edges)

    def get_note(self, id):
        self._log("get_note", id=id)
        for n in self._notes.values():
            if n.id == id:
                return n
        raise Boom(f"no note {id}")

    def get_all_notes(self, **kw):
        self._log("get_all_notes", **kw)
        if kw.get("forum"):
            return [FakeNote(id=kw["forum"],
                             details={"replies": list(self._replies)})]
        n = self._notes.get(kw.get("number"))
        return [n] if n else []

    def get_attachment(self, field_name, id=None, **kw):
        """Signature mirrors v2 exactly: field_name first."""
        self._log("get_attachment", field_name=field_name, id=id, **kw)
        if field_name != "pdf":
            raise Boom(f"no attachment named {field_name}")
        return self._pdf

    def get_invitation(self, id):
        self._log("get_invitation", id=id)
        if self._invitation is None:
            raise Boom(f"no invitation {id}")
        return self._invitation

    def get_groups(self, **kw):
        self._log("get_groups", **kw)
        return list(self._groups)
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_or_client.py`:

```python
import json
from pathlib import Path

import pytest

from refereekit.openreview import client as orclient
from refereekit.session import Session
from tests.openreview_fakes import (FakeEdge, FakeGroup, FakeNote, FakeORClient)

VENUE = "Test.cc/2027/Conference"


def _sub(number=42, nid="note-42", title="A Paper About Things", pdf=True):
    content = {"title": {"value": title}}
    if pdf:
        content["pdf"] = {"value": "/pdf/aaa.pdf"}
    return FakeNote(id=nid, number=number, content=content)


def _client(**kw):
    notes = kw.pop("notes", {42: _sub()})
    return FakeORClient(notes=notes, **kw)


# ---- assignments

def test_list_assignments_returns_number_and_title():
    c = _client(edges=[FakeEdge(head="note-42")])
    got = orclient.list_assignments(c, VENUE)
    assert [(a.number, a.title, a.forum) for a in got] == [
        (42, "A Paper About Things", "note-42")]


def test_list_assignments_queries_the_assignment_invitation_with_our_profile():
    c = _client(edges=[FakeEdge(head="note-42")])
    orclient.list_assignments(c, VENUE)
    kw = c.kwargs_for("get_all_edges")[0]
    assert kw["invitation"] == f"{VENUE}/Reviewers/-/Assignment"
    assert kw["tail"] == "~Test_User1"
    assert "limit" not in kw and "offset" not in kw   # v2 streams


def test_list_assignments_sorts_by_paper_number():
    notes = {7: _sub(7, "note-7", "Seven"), 42: _sub(42, "note-42", "Fortytwo")}
    c = _client(notes=notes,
                edges=[FakeEdge(head="note-42"), FakeEdge(head="note-7")])
    assert [a.number for a in orclient.list_assignments(c, VENUE)] == [7, 42]


def test_no_assignments_is_an_empty_list_not_an_error():
    assert orclient.list_assignments(_client(edges=[]), VENUE) == []


def test_edge_failure_becomes_an_ORError_naming_the_venue():
    c = _client(raise_on={"get_all_edges"})
    with pytest.raises(orclient.ORError, match="check the venue id"):
        orclient.list_assignments(c, VENUE)


# ---- submission

def test_fetch_submission_returns_pdf_bytes_and_forum_id():
    c = _client()
    pdf, forum = orclient.fetch_submission(c, VENUE, 42)
    assert pdf == b"%PDF-1.4 fake"
    assert forum == "note-42"


def test_fetch_submission_passes_field_name_by_keyword():
    """v2 is get_attachment(field_name, id=...), the reverse of the v1 example
    that circulates widely. Positional args send the note id as the field name
    and 404. This test is the guard against that regression."""
    c = _client()
    orclient.fetch_submission(c, VENUE, 42)
    kw = c.kwargs_for("get_attachment")[0]
    assert kw["field_name"] == "pdf"
    assert kw["id"] == "note-42"


def test_fetch_submission_queries_by_number_not_by_fetching_everything():
    c = _client()
    orclient.fetch_submission(c, VENUE, 42)
    kw = c.kwargs_for("get_all_notes")[0]
    assert kw["number"] == 42
    assert kw["invitation"] == f"{VENUE}/-/Submission"


def test_unassigned_submission_says_so():
    c = _client(notes={})
    with pytest.raises(orclient.ORError, match="not assigned to you"):
        orclient.fetch_submission(c, VENUE, 42)


def test_submission_without_a_pdf_says_so():
    c = _client(notes={42: _sub(pdf=False)})
    with pytest.raises(orclient.ORError, match="no pdf attachment"):
        orclient.fetch_submission(c, VENUE, 42)


# ---- form

def test_fetch_form_parses_the_invitation():
    inv = json.loads(Path("tests/fixtures/openreview_default_form.json").read_text())
    c = _client(invitation=inv)
    form = orclient.fetch_form(c, VENUE, 42)
    assert [f.name for f in form.prose_fields()] == ["title", "review"]
    assert c.kwargs_for("get_invitation")[0]["id"] == \
        f"{VENUE}/Submission42/-/Official_Review"


def test_fetch_form_is_none_before_the_review_stage_opens():
    """No invitation yet is normal, not an error: the referee still wants the
    pdf, which is the part they need first."""
    assert orclient.fetch_form(_client(invitation=None), VENUE, 42) is None


# ---- our own anonymous groups

def test_our_group_ids_queries_by_prefix_and_signatory():
    c = _client(groups=[FakeGroup(id=f"{VENUE}/Submission42/Reviewer_abc1")])
    got = orclient.our_group_ids(c, VENUE, 42)
    assert got == {f"{VENUE}/Submission42/Reviewer_abc1"}
    kw = c.kwargs_for("get_groups")[0]
    assert kw["prefix"] == f"{VENUE}/Submission42/Reviewer_"
    assert kw["signatory"] == "~Test_User1"


def test_our_group_ids_is_empty_when_the_lookup_fails():
    c = _client(raise_on={"get_groups"})
    assert orclient.our_group_ids(c, VENUE, 42) == set()


# ---- replies

def _reply(nid, tcdate, sigs, invitation, body="Thanks for the review."):
    return {"id": nid, "tcdate": tcdate, "signatures": sigs,
            "invitations": [invitation], "content": {"comment": {"value": body}}}


def test_fetch_replies_flattens_the_details_replies():
    r = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    assert orclient.fetch_replies(_client(replies=[r]), "note-42") == [r]


def test_store_replies_names_files_by_note_id_and_tcdate(tmp_path):
    s = Session.create(tmp_path, "p")
    r = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    written, skipped = orclient.store_replies(s, [r], set())
    assert written == ["r1-1700000000000.txt"] and skipped == []
    assert (s.theirs_dir / "r1-1700000000000.txt").exists()


def test_stored_reply_header_says_what_it_is(tmp_path):
    s = Session.create(tmp_path, "p")
    r = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    orclient.store_replies(s, [r], set())
    text = (s.theirs_dir / "r1-1700000000000.txt").read_text()
    assert text.startswith("# openreview note r1 by ~Author_One1 at 2023-11-14")
    assert "# invitation: X/-/Rebuttal" in text
    assert "Thanks for the review." in text


def test_refetching_an_unchanged_reply_is_skipped_not_an_error(tmp_path):
    """put_theirs is write-once, so a naive re-fetch would raise
    ProvenanceError. Same note, same tcdate, same filename: skip it."""
    s = Session.create(tmp_path, "p")
    r = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    orclient.store_replies(s, [r], set())
    written, skipped = orclient.store_replies(s, [r], set())
    assert written == [] and skipped == ["r1-1700000000000.txt"]


def test_a_revised_reply_becomes_a_second_file_and_both_remain(tmp_path):
    """A rebuttal edited during the discussion period has a new tcdate, so it
    is a new file. Both versions are kept and the change is visible."""
    s = Session.create(tmp_path, "p")
    first = _reply("r1", 1700000000000, ["~Author_One1"], "X/-/Rebuttal", "v1")
    second = _reply("r1", 1700009999000, ["~Author_One1"], "X/-/Rebuttal", "v2")
    orclient.store_replies(s, [first], set())
    written, _ = orclient.store_replies(s, [second], set())
    assert written == ["r1-1700009999000.txt"]
    assert (s.theirs_dir / "r1-1700000000000.txt").read_text().endswith("v1\n")
    assert (s.theirs_dir / "r1-1700009999000.txt").read_text().endswith("v2\n")


def test_our_own_review_never_lands_in_theirs(tmp_path):
    """Storing our own review under theirs/ would recreate exactly the
    our-draft-versus-their-report confusion that ours/ and theirs/ exist to
    prevent."""
    s = Session.create(tmp_path, "p")
    mine = f"{VENUE}/Submission42/Reviewer_abc1"
    ours = _reply("r-mine", 1700000000000, [mine], "X/-/Official_Review")
    theirs = _reply("r-them", 1700000000000, ["~Author_One1"], "X/-/Rebuttal")
    coreviewer = _reply("r-co", 1700000000000,
                        [f"{VENUE}/Submission42/Reviewer_zzz9"],
                        "X/-/Official_Review")
    written, _ = orclient.store_replies(s, [ours, theirs, coreviewer], {mine})
    assert sorted(written) == ["r-co-1700000000000.txt",
                              "r-them-1700000000000.txt"]
    assert not (s.theirs_dir / "r-mine-1700000000000.txt").exists()


def test_make_client_without_credentials_says_which_variables(monkeypatch):
    monkeypatch.setenv("OPENREVIEW_USERNAME", "")
    monkeypatch.delenv("OPENREVIEW_PASSWORD", raising=False)
    with pytest.raises(orclient.ORError,
                       match="OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD"):
        orclient.make_client()


def _stub_openreview(monkeypatch, factory):
    """Stand in for the openreview package so these tests run identically with
    the extra installed and without it."""
    import sys
    import types
    mod = types.ModuleType("openreview")
    mod.api = types.SimpleNamespace(OpenReviewClient=factory)
    monkeypatch.setitem(sys.modules, "openreview", mod)


def test_make_client_error_never_echoes_the_password(monkeypatch):
    """A credential in an exception message reaches every log that catches it."""
    def explode(**kw):
        raise RuntimeError(f"401 rejected {kw['username']}:{kw['password']}")
    _stub_openreview(monkeypatch, explode)
    monkeypatch.setenv("OPENREVIEW_USERNAME", "someone@example.com")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "hunter2-do-not-print")
    with pytest.raises(orclient.ORError) as ei:
        orclient.make_client()
    assert "hunter2" not in str(ei.value)
    assert "someone@example.com" in str(ei.value)


def test_make_client_passes_the_baseurl_through(monkeypatch):
    seen = {}
    _stub_openreview(monkeypatch, lambda **kw: seen.update(kw) or "client")
    monkeypatch.setenv("OPENREVIEW_USERNAME", "u")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "p")
    assert orclient.make_client("https://devapi2.openreview.net") == "client"
    assert seen["baseurl"] == "https://devapi2.openreview.net"


def test_make_client_without_the_extra_names_the_install_command(monkeypatch):
    import sys
    # A None entry makes the import fail the same way an absent package does.
    monkeypatch.setitem(sys.modules, "openreview", None)
    monkeypatch.setenv("OPENREVIEW_USERNAME", "u")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "p")
    with pytest.raises(orclient.ORError, match=r'pip install -e "\.\[openreview\]"'):
        orclient.make_client()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_or_client.py -v`
Expected: FAIL, `ImportError: cannot import name 'client' from 'refereekit.openreview'`

- [ ] **Step 4: Implement `client.py`**

Create `refereekit/openreview/client.py`:

```python
"""The only module in refereekit that talks to OpenReview.

Every function takes an already-constructed client, so tests inject a fake and
the rest of the package stays offline. That is the same shape ingest already
gives the codebase: the network lives at the edge, and everything downstream is
a pure function of local data.

Read-only by design. There is no post_note_edit call here, so refereekit cannot
write to OpenReview: posting is not one bug away, the code does not exist.
"""
import datetime
import os
from dataclasses import dataclass

from .form import ReviewForm, parse_form

BASEURL = "https://api2.openreview.net"


class ORError(RuntimeError):
    """An OpenReview failure, translated at this boundary.

    cli.py catches this and never imports a third-party exception type, so the
    CLI keeps working with the openreview extra uninstalled.
    """


@dataclass
class Assignment:
    number: int
    forum: str      # the submission note id
    title: str


def make_client(baseurl: str = BASEURL):
    """Credentials come from the environment only: a password in a flag lands
    in shell history and in the process table."""
    try:
        from openreview import api as openreview_api
    except ImportError as e:
        raise ORError(
            'openreview support requires: pip install -e ".[openreview]"') from e
    username = os.environ.get("OPENREVIEW_USERNAME")
    password = os.environ.get("OPENREVIEW_PASSWORD")
    # An empty value is as unusable as an absent one, so both take this branch.
    if not username or not password:
        raise ORError("set OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD")
    try:
        return openreview_api.OpenReviewClient(
            baseurl=baseurl, username=username, password=password)
    except Exception as e:
        # Deliberately broad: openreview raises its own type and this module is
        # the boundary that keeps it from escaping. The message omits both the
        # exception and the password, so no credential can reach a log.
        raise ORError(f"openreview login failed for {username}") from e


def _content_value(note, key: str, default: str = ""):
    """A v2 note's content is {field: {"value": ...}}."""
    got = (getattr(note, "content", None) or {}).get(key)
    if isinstance(got, dict):
        return got.get("value", default)
    return default


def profile_id(client) -> str:
    try:
        return client.get_profile().id
    except Exception as e:
        raise ORError(f"could not read your openreview profile: {e}") from e


def list_assignments(client, venue: str) -> list:
    """Assignments are edges from the reviewer's profile to the submission.

    An edge gives head (the submission id) but neither number nor title, so
    each head is resolved to print a list the referee can act on.
    """
    me = profile_id(client)
    try:
        edges = client.get_all_edges(
            invitation=f"{venue}/Reviewers/-/Assignment", tail=me)
    except Exception as e:
        raise ORError(
            f"no venue {venue}; check the venue id, "
            f"e.g. ICLR.cc/2027/Conference") from e
    out = []
    for edge in edges:
        try:
            note = client.get_note(edge.head)
        except Exception as e:
            raise ORError(f"could not read submission {edge.head}: {e}") from e
        out.append(Assignment(number=note.number, forum=note.id,
                              title=_content_value(note, "title")))
    out.sort(key=lambda a: a.number)
    return out


def fetch_submission(client, venue: str, number: int) -> tuple:
    """Returns (pdf bytes, forum id)."""
    try:
        subs = client.get_all_notes(
            invitation=f"{venue}/-/Submission", number=number)
    except Exception as e:
        raise ORError(f"could not read submission {number} at {venue}: {e}") from e
    if not subs:
        # An unassigned paper and a nonexistent one both come back empty,
        # because readers are restricted to the assigned committee.
        raise ORError(f"submission {number} is not assigned to you at {venue}")
    note = subs[0]
    if not _content_value(note, "pdf"):
        raise ORError(f"submission {number} has no pdf attachment")
    try:
        # v2 takes field_name FIRST: get_attachment(field_name, id=None, ...).
        # The widely-copied v1 example is get_attachment(note.id, 'pdf'), whose
        # argument order is reversed. Passing positionally here would send the
        # note id as the field name and 404. Both by keyword, always.
        pdf = client.get_attachment(field_name="pdf", id=note.id)
    except Exception as e:
        raise ORError(
            f"could not download the pdf for submission {number}: {e}") from e
    return pdf, note.id


def fetch_form(client, venue: str, number: int) -> ReviewForm | None:
    """None when the review stage has not opened yet, which is not an error."""
    inv_id = f"{venue}/Submission{number}/-/Official_Review"
    try:
        inv = client.get_invitation(inv_id)
    except Exception:
        return None
    edit = inv.get("edit") if isinstance(inv, dict) else getattr(inv, "edit", None)
    return parse_form({"id": inv_id, "edit": edit or {}})


def our_group_ids(client, venue: str, number: int) -> set:
    """Our own anonymous reviewer group ids for this submission.

    A reply signed by one of these is ours, not theirs. Returns an empty set on
    failure: the consequence is that a reply of ours could be stored under
    theirs/, which the caller reports, rather than the whole fetch failing.
    """
    try:
        groups = client.get_groups(
            prefix=f"{venue}/Submission{number}/Reviewer_",
            signatory=profile_id(client))
    except Exception:
        return set()
    return {g.id for g in groups}


def fetch_replies(client, forum: str) -> list:
    """Every reply on the submission's forum: co-reviewers' official reviews,
    author comments, and our own review once posted."""
    try:
        notes = client.get_all_notes(forum=forum, details="replies")
    except Exception as e:
        raise ORError(f"could not read the discussion for {forum}: {e}") from e
    replies = []
    for n in notes:
        details = getattr(n, "details", None) or {}
        replies.extend(details.get("replies") or [])
    return replies


def _safe(s) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(s))


def _iso(tcdate) -> str:
    """OpenReview's own creation time, epoch milliseconds. This reads no local
    clock, so a re-fetch produces the same filename and the same header."""
    if not tcdate:
        return "unknown"
    return datetime.datetime.fromtimestamp(
        int(tcdate) / 1000, tz=datetime.timezone.utc).isoformat()


def _render_reply(r: dict) -> str:
    sigs = ", ".join(r.get("signatures") or []) or "unknown"
    inv = ", ".join(r.get("invitations") or []) or "unknown"
    body = []
    for k, v in (r.get("content") or {}).items():
        body.append(f"{k}: {v.get('value') if isinstance(v, dict) else v}")
    return (f"# openreview note {r.get('id', 'unknown')} by {sigs} "
            f"at {_iso(r.get('tcdate'))}\n"
            f"# invitation: {inv}\n\n" + "\n\n".join(body) + "\n")


def store_replies(session, replies: list, skip_signatures: set) -> tuple:
    """Write received notes to theirs/. Returns (written names, skipped names).

    Named <note-id>-<tcdate>.txt. A rebuttal revised during the discussion
    period has a new tcdate and so becomes a new file: both versions are kept
    and the change is visible. That keeps put_theirs write-once rather than
    working around it. An identical re-fetch produces a name that already
    exists, which put_theirs would reject, so it is skipped instead.

    A reply signed by one of our own anonymous reviewer groups is ours, not
    theirs. Storing it here would recreate the confusion between our draft and
    someone else's report that ours/ and theirs/ exist to prevent.
    """
    written, skipped = [], []
    for r in replies:
        if any(s in skip_signatures for s in (r.get("signatures") or [])):
            continue
        name = f"{_safe(r.get('id', 'unknown'))}-{r.get('tcdate', 0)}.txt"
        if (session.theirs_dir / name).exists():
            skipped.append(name)
            continue
        session.put_theirs(name, _render_reply(r))
        written.append(name)
    return written, skipped
```

- [ ] **Step 5: Extend the subpackage `__init__.py`**

Replace `refereekit/openreview/__init__.py`:

```python
from .form import Field, ReviewForm, parse_form
from .client import Assignment, ORError
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_or_client.py -v`
Expected: PASS, 24 tests.

- [ ] **Step 7: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: all passing.

- [ ] **Step 8: Confirm the read-only constraint holds**

Run: `grep -rn "post_note_edit\|put_attachment\|post_edge" refereekit/`
Expected: no output. If anything matches, a write path has crept in and the task is not done.

- [ ] **Step 9: Commit**

```bash
git add refereekit/openreview/client.py refereekit/openreview/__init__.py \
        tests/openreview_fakes.py tests/test_or_client.py
git commit -m "feat: openreview fetch boundary, read-only

Every network call lives here and each function takes an injected client,
so the suite runs with no credentials. No post_note_edit call exists, so
posting is not one bug away.

Two details worth pinning. get_attachment on v2 takes field_name first,
the reverse of the v1 example that circulates widely, and calling it
positionally sends the note id as the field name and 404s; a test asserts
the keyword call. And received notes are named by note id plus tcdate, so
a revised rebuttal becomes a new file rather than colliding with the
put_theirs write-once guard, while a reply we signed ourselves is kept out
of theirs/ entirely.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Fill the form's prose fields

Draft each prose field from the verified claim pool via `drafts.report`, and leave every rating empty. The assertion that choice fields stay empty is the load-bearing test in this plan.

**Files:**
- Create: `refereekit/openreview/fill.py`
- Test: `tests/test_or_fill.py`

**Interfaces:**
- Consumes: `form.ReviewForm` (Task 1), `drafts.report(..., field_instruction=...)` (Task 2).
- Produces:
  - `FilledForm(values: dict, blanks: list, flags: list)` dataclass
  - `fill(session, form, *, backend, style_path, lengths=None, memory=None, venue=None) -> FilledForm`
  - `to_markdown(form, filled: FilledForm) -> str`
  - `to_json(filled: FilledForm) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_or_fill.py`:

```python
import json
from pathlib import Path

import pytest

from refereekit.ingest import ingest
from refereekit.llm import FakeBackend
from refereekit.openreview import fill as orfill
from refereekit.openreview import form as orform
from refereekit.session import Session
from refereekit.types import Claim

STYLE = "style/STYLE.md"


def _form(name="openreview_iclr_form.json"):
    return orform.parse_form(
        json.loads((Path("tests/fixtures") / name).read_text()))


def _session(tmp_path, real_pdf_path):
    s = Session.create(tmp_path, "p")
    s.save_doc(ingest(real_pdf_path))
    s.record_claim(Claim("", "page", "3"))
    s.set_state("verdict", {"recommend": "minor"})
    return s


def test_every_prose_field_gets_drafted(tmp_path, real_pdf_path):
    s = _session(tmp_path, real_pdf_path)
    got = orfill.fill(s, _form(), backend=FakeBackend("prose here"),
                      style_path=STYLE)
    assert sorted(got.values) == ["confidential_comment", "strengths",
                                  "summary", "weaknesses"]
    assert got.values["summary"] == "prose here"


def test_no_choice_field_is_ever_filled(tmp_path, real_pdf_path):
    """The load-bearing assertion. Verification is substring matching: it
    cannot justify a soundness of 3 over a 4. If drafting ever starts filling
    ratings, this fails loudly."""
    s = _session(tmp_path, real_pdf_path)
    form = _form()
    got = orfill.fill(s, form, backend=FakeBackend("prose"), style_path=STYLE)
    for f in form.choice_fields():
        assert f.name not in got.values
    payload = json.loads(orfill.to_json(got))
    for name in ("soundness", "presentation", "contribution", "rating",
                 "confidence"):
        assert payload[name] == ""


def test_blanks_list_every_field_the_referee_must_fill(tmp_path, real_pdf_path):
    s = _session(tmp_path, real_pdf_path)
    got = orfill.fill(s, _form(), backend=FakeBackend("prose"), style_path=STYLE)
    names = {f.name for f in got.blanks}
    assert {"soundness", "rating", "confidence", "supplementary"} <= names
    assert "summary" not in names


def test_the_venue_description_reaches_the_prompt(tmp_path, real_pdf_path):
    """A field's instruction is the venue telling the reviewer what belongs
    there: better guidance than anything we could invent."""
    s = _session(tmp_path, real_pdf_path)
    seen = []
    backend = FakeBackend(lambda p: seen.append(p) or "prose")
    orfill.fill(s, _form(), backend=backend, style_path=STYLE)
    joined = "\n".join(seen)
    assert "Summarize the paper in your own words." in joined
    assert "List the weaknesses of the submission." in joined
    assert "Write the 'summary' field" in joined


def test_one_backend_call_per_prose_field(tmp_path, real_pdf_path):
    """Per-field calls mean a field that fails does not lose the others."""
    s = _session(tmp_path, real_pdf_path)
    calls = []
    backend = FakeBackend(lambda p: calls.append(p) or "prose")
    orfill.fill(s, _form(), backend=backend, style_path=STYLE)
    assert len(calls) == 4


def test_length_applies_only_to_its_own_field(tmp_path, real_pdf_path):
    """Passing the whole --length map to every call would tell each one about
    lengths for sections it is not writing."""
    s = _session(tmp_path, real_pdf_path)
    seen = {}
    def canned(prompt):
        which = next(n for n in ("summary", "strengths", "weaknesses",
                                 "confidential_comment")
                     if f"'{n}' field" in prompt)
        seen[which] = prompt
        return "prose"
    orfill.fill(s, _form(), backend=FakeBackend(canned), style_path=STYLE,
                lengths={"summary": "short"})
    assert "summary=short" in seen["summary"]
    assert "summary=short" not in seen["weaknesses"]


def test_unknown_length_name_is_an_error(tmp_path, real_pdf_path):
    """A typo, or a form that differs from the one the referee expected. Both
    are worth hearing about rather than silently ignoring."""
    s = _session(tmp_path, real_pdf_path)
    with pytest.raises(ValueError, match="nosuchfield"):
        orfill.fill(s, _form(), backend=FakeBackend("x"), style_path=STYLE,
                    lengths={"nosuchfield": "short"})


def test_flags_are_deduplicated_across_fields(tmp_path, real_pdf_path):
    """The same unpooled anchor cited in two fields is one problem, not two."""
    s = _session(tmp_path, real_pdf_path)
    got = orfill.fill(s, _form(), backend=FakeBackend("See p. 999 for this."),
                      style_path=STYLE)
    assert len(got.flags) == 1
    assert got.flags[0].anchor == "999"


def test_markdown_shows_drafted_prose_and_the_options_to_choose_from(
        tmp_path, real_pdf_path):
    s = _session(tmp_path, real_pdf_path)
    form = _form()
    got = orfill.fill(s, form, backend=FakeBackend("drafted prose"),
                      style_path=STYLE)
    md = orfill.to_markdown(form, got)
    assert "## summary" in md and "drafted prose" in md
    assert "## rating" in md
    assert "8: accept, good paper" in md
    assert "fill in yourself" in md


def test_markdown_keeps_the_venue_field_order(tmp_path, real_pdf_path):
    s = _session(tmp_path, real_pdf_path)
    form = _form()
    md = orfill.to_markdown(form, orfill.fill(
        s, form, backend=FakeBackend("p"), style_path=STYLE))
    assert md.index("## summary") < md.index("## weaknesses") < md.index("## rating")


def test_default_form_works_too(tmp_path, real_pdf_path):
    """No venue-specific code: the plain default form goes through unchanged."""
    s = _session(tmp_path, real_pdf_path)
    form = _form("openreview_default_form.json")
    got = orfill.fill(s, form, backend=FakeBackend("prose"), style_path=STYLE)
    assert sorted(got.values) == ["review", "title"]
    assert {f.name for f in got.blanks} == {"rating", "confidence"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_or_fill.py -v`
Expected: FAIL, `ImportError: cannot import name 'fill' from 'refereekit.openreview'`

- [ ] **Step 3: Implement `fill.py`**

Create `refereekit/openreview/fill.py`:

```python
"""Draft the prose fields of an OpenReview review form.

Numeric and enum fields are never filled. Verification is substring matching:
it can confirm that a quoted phrase is on a page, and it cannot tell a
soundness of 3 from a 4. Those fields come back empty for the referee.

Drafting goes through drafts.report rather than reimplementing prompt
construction, so the voice guide, the claim pool, the verified-versus-pointer
distinction, and _verify_prose anchor checking all apply unchanged.
"""
import json
from dataclasses import dataclass, field as _field

from .. import drafts


@dataclass
class FilledForm:
    values: dict                      # field name -> drafted prose
    blanks: list                      # Field objects the referee must fill
    flags: list = _field(default_factory=list)


def _instruction(f) -> str:
    lines = [f"Write the '{f.name}' field of an OpenReview review form."]
    if f.description:
        lines.append(f"The venue's instruction for this field: {f.description}")
    if f.max_length:
        lines.append(f"Hard limit: {f.max_length} characters.")
    return "\n".join(lines)


def _dedupe(flags: list) -> list:
    """The same unpooled anchor cited in two fields is one problem, not two."""
    seen, out = set(), []
    for fl in flags:
        key = (fl.kind, fl.anchor, fl.reason)
        if key not in seen:
            seen.add(key)
            out.append(fl)
    return out


def fill(session, form, *, backend, style_path, lengths=None,
         memory=None, venue=None) -> FilledForm:
    """One backend call per prose field.

    Per-field calls, rather than one call for the whole form, so each field
    gets the venue's own instruction and so a field that fails does not lose
    the others.
    """
    lengths = dict(lengths or {})
    unknown = sorted(set(lengths) - {f.name for f in form.fields})
    if unknown:
        raise ValueError(
            f"--length names no field in this form: {', '.join(unknown)}")
    verdict = session.get_state("verdict", {})
    values, flags = {}, []
    for f in form.prose_fields():
        # Only this field's length: the whole map would tell each call about
        # sections it is not writing.
        own = {f.name: lengths[f.name]} if f.name in lengths else {}
        d = drafts.report(session, verdict, own, backend=backend,
                          style_path=style_path, memory=memory, venue=venue,
                          field_instruction=_instruction(f))
        values[f.name] = d.text
        flags.extend(d.flags)
    return FilledForm(values=values,
                      blanks=form.choice_fields() + form.other_fields(),
                      flags=_dedupe(flags))


def _blank_hint(f) -> str:
    if f.enum:
        opts = "; ".join(f"{v}: {d}" if d else str(v) for v, d in f.enum)
        return f"(fill in yourself. options: {opts})"
    return "(fill in yourself)"


def to_markdown(form, filled: FilledForm) -> str:
    """For reading and pasting into the web form, in the venue's field order."""
    out = [f"# {form.invitation_id}", ""]
    for f in form.fields:
        out.append(f"## {f.name}")
        if f.description:
            out.append(f"<!-- {f.description} -->")
        out.append("")
        out.append(filled.values.get(f.name) or _blank_hint(f))
        out.append("")
    return "\n".join(out)


def to_json(filled: FilledForm) -> str:
    """Field name to value. A blank field appears with an empty string, so the
    mapping lists every field on the form and a reader sees what is missing."""
    payload = dict(filled.values)
    for f in filled.blanks:
        payload.setdefault(f.name, "")
    return json.dumps(payload, indent=2)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_or_fill.py -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: all passing.

- [ ] **Step 6: Commit**

```bash
git add refereekit/openreview/fill.py tests/test_or_fill.py
git commit -m "feat: draft the prose fields of a review form, leave ratings blank

One backend call per prose field, each carrying the venue's own
description of that field, so a failure loses one field rather than all
of them. Every enum field comes back empty: substring verification cannot
justify a soundness of 3 over a 4, and a test asserts it stays that way.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Summarize the authors' responses

A reading aid, not a verdict. It reports what the response addresses, what it does not, and what needs re-checking against the paper.

**Files:**
- Create: `refereekit/openreview/responses.py`
- Test: `tests/test_or_responses.py`

**Interfaces:**
- Consumes: `llm.complete(prompt, *, backend, manuscript_ok=True)` (existing).
- Produces:
  - `build_prompt(our_review: str, received: list[str]) -> str`
  - `analyze(our_review: str, received: list[str], *, backend) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_or_responses.py`:

```python
import pytest

from refereekit.llm import FakeBackend, RetentionError
from refereekit.openreview import responses


def test_prompt_carries_our_review_and_what_we_received():
    p = responses.build_prompt("we asked about Eq. (3)", ["the authors replied"])
    assert "we asked about Eq. (3)" in p
    assert "the authors replied" in p


def test_prompt_forbids_recommending_a_score():
    """The output is a reading aid. A rating is the referee's to decide."""
    p = responses.build_prompt("ours", ["theirs"])
    assert "Do not recommend a rating" in p


def test_prompt_asks_for_the_three_buckets():
    p = responses.build_prompt("ours", ["theirs"])
    for want in ("does not address", "should re-check"):
        assert want in p


def test_prompt_ends_with_the_stale_document_warning():
    """doc.json holds the version originally fetched, so a claim about a
    revised manuscript cannot be verified against it."""
    p = responses.build_prompt("ours", ["theirs"])
    assert p.rstrip().endswith(
        "doc.json, which holds the version originally fetched.")


def test_multiple_received_notes_are_separated():
    p = responses.build_prompt("ours", ["first note", "second note"])
    assert "first note" in p and "second note" in p
    assert p.index("first note") < p.index("second note")


def test_no_draft_yet_is_stated_not_left_blank():
    """Reading the responses before drafting is a legitimate order of work."""
    p = responses.build_prompt("   ", ["theirs"])
    assert "we have not drafted our review yet" in p


def test_analyze_returns_the_backend_text():
    assert responses.analyze("ours", ["theirs"],
                             backend=FakeBackend("analysis")) == "analysis"


def test_analyze_with_nothing_received_is_an_error():
    """An empty output file would read as 'the authors said nothing'."""
    with pytest.raises(ValueError, match="nothing to analyze"):
        responses.analyze("ours", [], backend=FakeBackend("x"))


def test_analyze_refuses_a_backend_that_is_not_zero_retention():
    """Author responses are manuscript-adjacent text."""
    with pytest.raises(RetentionError):
        responses.analyze("ours", ["theirs"],
                          backend=FakeBackend("x", zero_retention=False))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_or_responses.py -v`
Expected: FAIL, `ImportError: cannot import name 'responses' from 'refereekit.openreview'`

- [ ] **Step 3: Implement `responses.py`**

Create `refereekit/openreview/responses.py`:

```python
"""Summarize the authors' responses against our own review.

A reading aid, not a verdict. It contains no rating and no recommendation:
what the response is worth is the referee's judgment.
"""
from ..llm import complete

_STALE_NOTE = ("NOTE: claims about a revised manuscript cannot be verified "
               "against doc.json, which holds the version originally fetched.")


def build_prompt(our_review: str, received: list) -> str:
    ours = our_review.strip() or "(we have not drafted our review yet)"
    return (
        "You are helping a referee read what came back on a submission.\n\n"
        f"=== OUR REVIEW ===\n{ours}\n\n"
        "=== RECEIVED FROM OTHERS ===\n"
        + "\n\n- - -\n\n".join(received) + "\n\n"
        "Report, in this order:\n"
        "1. Points we raised that the response addresses, and how.\n"
        "2. Points we raised that the response does not address.\n"
        "3. Factual claims the response makes about the manuscript that we "
        "should re-check against the paper.\n\n"
        "Do not recommend a rating, a score, or an accept/reject decision.\n\n"
        f"End with this line verbatim:\n{_STALE_NOTE}"
    )


def analyze(our_review: str, received: list, *, backend) -> str:
    """Author responses are manuscript-adjacent text, so this goes only to a
    zero-retention backend, on the same path as the manuscript itself."""
    if not received:
        raise ValueError("no received notes in theirs/; nothing to analyze")
    return complete(build_prompt(our_review, received), backend=backend,
                    manuscript_ok=True)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_or_responses.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: all passing.

- [ ] **Step 6: Commit**

```bash
git add refereekit/openreview/responses.py tests/test_or_responses.py
git commit -m "feat: summarize author responses against our own review

Three buckets: addressed, not addressed, and claims to re-check against
the paper. No rating and no recommendation, and it ends by saying that a
claim about a revised manuscript cannot be checked against doc.json,
which holds the version originally fetched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: CLI wiring and documentation

Three subcommands, plus the README section including the venue LLM policies.

**Files:**
- Modify: `refereekit/cli.py`
- Modify: `README.md`
- Test: `tests/test_cli_openreview.py`

**Interfaces:**
- Consumes: everything from Tasks 1 through 5.
- Produces: `or-fetch`, `or-draft`, `or-responses` subcommands.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_openreview.py`:

```python
import json
from pathlib import Path

from refereekit.cli import main
from refereekit.ingest import ingest
from refereekit.openreview import client as orclient
from refereekit.session import Session
from refereekit.types import Claim
from tests.openreview_fakes import FakeEdge, FakeGroup, FakeNote, FakeORClient

VENUE = "Test.cc/2027/Conference"


def _fake_client(real_pdf_path, **kw):
    note = FakeNote(id="note-42", number=42,
                    content={"title": {"value": "A Paper"},
                             "pdf": {"value": "/pdf/a.pdf"}})
    inv = json.loads(
        Path("tests/fixtures/openreview_iclr_form.json").read_text())
    defaults = dict(notes={42: note}, edges=[FakeEdge(head="note-42")],
                    invitation=inv, pdf=real_pdf_path.read_bytes(),
                    groups=[FakeGroup(id=f"{VENUE}/Submission42/Reviewer_me1")])
    defaults.update(kw)
    return FakeORClient(**defaults)


def _patch(monkeypatch, client):
    monkeypatch.setattr(orclient, "make_client", lambda baseurl=None: client)


def test_or_fetch_lists_assignments(monkeypatch, tmp_path, real_pdf_path, capsys):
    _patch(monkeypatch, _fake_client(real_pdf_path))
    rc = main(["or-fetch", "--venue", VENUE, "--session", str(tmp_path / "s")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "42" in out and "A Paper" in out


def test_or_fetch_with_no_assignments_says_so(monkeypatch, tmp_path,
                                              real_pdf_path, capsys):
    _patch(monkeypatch, _fake_client(real_pdf_path, edges=[]))
    rc = main(["or-fetch", "--venue", VENUE, "--session", str(tmp_path / "s")])
    assert rc == 0
    assert "no assignments" in capsys.readouterr().out


def test_or_fetch_number_writes_pdf_doc_and_form(monkeypatch, tmp_path,
                                                 real_pdf_path, capsys):
    _patch(monkeypatch, _fake_client(real_pdf_path))
    sess = tmp_path / "s"
    rc = main(["or-fetch", "--venue", VENUE, "--number", "42",
               "--session", str(sess)])
    assert rc == 0
    assert (sess / "paper.pdf").exists()
    assert (sess / "doc.json").exists()
    form = json.loads((sess / "form.json").read_text())
    assert form["invitation_id"].endswith("Submission42/-/Official_Review")
    assert Session(sess).get_state("venue") == VENUE
    assert Session(sess).get_state("number") == 42


def test_or_fetch_stores_replies_but_not_our_own(monkeypatch, tmp_path,
                                                 real_pdf_path):
    mine = f"{VENUE}/Submission42/Reviewer_me1"
    replies = [
        {"id": "r-them", "tcdate": 1700000000000, "signatures": ["~Author_One1"],
         "invitations": [f"{VENUE}/Submission42/-/Rebuttal"],
         "content": {"comment": {"value": "We revised Sec. 3."}}},
        {"id": "r-mine", "tcdate": 1700000000000, "signatures": [mine],
         "invitations": [f"{VENUE}/Submission42/-/Official_Review"],
         "content": {"review": {"value": "my own review"}}},
    ]
    _patch(monkeypatch, _fake_client(real_pdf_path, replies=replies))
    sess = tmp_path / "s"
    assert main(["or-fetch", "--venue", VENUE, "--number", "42",
                 "--session", str(sess)]) == 0
    names = [p.name for p in (sess / "theirs").iterdir()]
    assert names == ["r-them-1700000000000.txt"]


def test_or_fetch_before_the_review_stage_still_gets_the_pdf(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    _patch(monkeypatch, _fake_client(real_pdf_path, invitation=None))
    sess = tmp_path / "s"
    rc = main(["or-fetch", "--venue", VENUE, "--number", "42",
               "--session", str(sess)])
    assert rc == 0
    assert (sess / "doc.json").exists()
    assert not (sess / "form.json").exists()
    assert "no review form yet" in capsys.readouterr().out


def test_or_fetch_reports_an_or_error_as_exit_2(monkeypatch, tmp_path, capsys):
    def boom(baseurl=None):
        raise orclient.ORError("set OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD")
    monkeypatch.setattr(orclient, "make_client", boom)
    rc = main(["or-fetch", "--venue", VENUE, "--session", str(tmp_path / "s")])
    assert rc == 2
    assert "OPENREVIEW_USERNAME" in capsys.readouterr().err


def test_or_fetch_baseurl_reaches_the_client(monkeypatch, tmp_path, real_pdf_path):
    seen = {}
    c = _fake_client(real_pdf_path)
    monkeypatch.setattr(orclient, "make_client",
                        lambda baseurl=None: seen.setdefault("u", baseurl) or c)
    main(["or-fetch", "--venue", VENUE, "--session", str(tmp_path / "s"),
          "--baseurl", "https://devapi2.openreview.net"])
    assert seen["u"] == "https://devapi2.openreview.net"


def test_or_fetch_on_a_download_that_is_not_a_pdf_exits_2(
        monkeypatch, tmp_path, real_pdf_path, capsys):
    """A truncated or error-page download must not leave a half-built session
    passing for a fetched paper."""
    _patch(monkeypatch, _fake_client(real_pdf_path, pdf=b"<html>error</html>"))
    sess = tmp_path / "s"
    rc = main(["or-fetch", "--venue", VENUE, "--number", "42",
               "--session", str(sess)])
    assert rc == 2
    assert not (sess / "doc.json").exists()
    assert capsys.readouterr().err.startswith("error:")


def _fetched_session(monkeypatch, tmp_path, real_pdf_path):
    _patch(monkeypatch, _fake_client(real_pdf_path))
    sess = tmp_path / "s"
    main(["or-fetch", "--venue", VENUE, "--number", "42", "--session", str(sess)])
    s = Session(sess)
    s.record_claim(Claim("", "page", "3"))
    s.set_state("verdict", {"recommend": "minor"})
    return sess


def test_or_draft_writes_markdown_and_json(monkeypatch, tmp_path,
                                           real_pdf_path, capsys):
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "Drafted prose.")
    rc = main(["or-draft", "--session", str(sess)])
    assert rc == 0
    md = (sess / "ours" / "openreview.md").read_text()
    assert "## summary" in md and "Drafted prose." in md
    payload = json.loads((sess / "ours" / "openreview.json").read_text())
    assert payload["summary"] == "Drafted prose."
    assert payload["rating"] == ""
    out = capsys.readouterr().out
    assert "to fill in yourself" in out and "rating" in out


def test_or_draft_without_a_form_says_to_fetch_first(tmp_path, capsys):
    s = Session.create(tmp_path, "s")
    rc = main(["or-draft", "--session", str(s.dir)])
    assert rc == 2
    assert "run or-fetch --number first" in capsys.readouterr().err


def test_or_draft_with_an_unknown_length_name_exits_2(monkeypatch, tmp_path,
                                                      real_pdf_path, capsys):
    sess = _fetched_session(monkeypatch, tmp_path, real_pdf_path)
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    rc = main(["or-draft", "--session", str(sess), "--length", "nope=short"])
    assert rc == 2
    assert "nope" in capsys.readouterr().err


def test_or_responses_writes_the_analysis(monkeypatch, tmp_path,
                                         real_pdf_path, capsys):
    mine = f"{VENUE}/Submission42/Reviewer_me1"
    replies = [{"id": "r-them", "tcdate": 1700000000000,
                "signatures": ["~Author_One1"],
                "invitations": [f"{VENUE}/Submission42/-/Rebuttal"],
                "content": {"comment": {"value": "We revised Sec. 3."}}}]
    _patch(monkeypatch, _fake_client(real_pdf_path, replies=replies))
    sess = tmp_path / "s"
    main(["or-fetch", "--venue", VENUE, "--number", "42", "--session", str(sess)])
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    monkeypatch.setenv("REFEREEKIT_FAKE_TEXT", "They addressed point one.")
    rc = main(["or-responses", "--session", str(sess)])
    assert rc == 0
    assert (sess / "ours" / "response-analysis.txt").read_text() == \
        "They addressed point one."


def test_or_responses_with_nothing_received_exits_2(tmp_path, capsys):
    s = Session.create(tmp_path, "s")
    rc = main(["or-responses", "--session", str(s.dir)])
    assert rc == 2
    assert "nothing to analyze" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli_openreview.py -v`
Expected: FAIL, `SystemExit: 2` from argparse: `invalid choice: 'or-fetch'`

- [ ] **Step 3: Add the three parsers**

In `refereekit/cli.py`, after the `review` parser block (currently ends at line 61 with `prv.add_argument("--style", default=None)`), add:

```python
    pof = sub.add_parser("or-fetch")
    pof.add_argument("--venue", required=True)
    pof.add_argument("--session", required=True)
    pof.add_argument("--number", type=int)
    pof.add_argument("--baseurl", default=None)
    pod = sub.add_parser("or-draft")
    pod.add_argument("--session", required=True)
    pod.add_argument("--length", action="append", default=[])
    pod.add_argument("--style", default=None)
    por = sub.add_parser("or-responses")
    por.add_argument("--session", required=True)
```

- [ ] **Step 4: Add the three handlers**

In `refereekit/cli.py`, immediately before the final `return 2` (currently line 164), add:

```python
    if args.cmd == "or-fetch":
        from .openreview import client as orclient
        from .openreview import form as orform
        try:
            c = orclient.make_client(args.baseurl or orclient.BASEURL)
            if args.number is None:
                found = orclient.list_assignments(c, args.venue)
                if not found:
                    print(f"no assignments for you at {args.venue}")
                    return 0
                for a in found:
                    print(f"  {a.number:>4}  {a.title}")
                print("Fetch one with: --number <N>")
                return 0
            sdir = Path(args.session)
            s = Session.create(sdir.parent, sdir.name)
            pdf_bytes, forum = orclient.fetch_submission(c, args.venue, args.number)
            pdf_path = s.dir / "paper.pdf"
            pdf_path.write_bytes(pdf_bytes)
            doc = ingest(pdf_path)
            s.save_doc(doc)
            print(f"fetched submission {args.number}: {len(doc.pages)} pages")
            s.set_state("venue", args.venue)
            s.set_state("number", args.number)
            s.set_state("forum", forum)
            # Best-effort from here. Before the review stage opens there is no
            # invitation, and before the rebuttal period there are no replies.
            # Neither is an error: the pdf is the part the referee needs first.
            form = orclient.fetch_form(c, args.venue, args.number)
            if form is None:
                print(f"no review form yet at {args.venue}/Submission"
                      f"{args.number}/-/Official_Review; skipping form.json")
            else:
                (s.dir / "form.json").write_text(orform.to_json(form))
                s.set_state("invitation_id", form.invitation_id)
                print(f"review form: {len(form.prose_fields())} prose field(s), "
                      f"{len(form.choice_fields())} to fill in yourself")
            replies = orclient.fetch_replies(c, forum)
            if not replies:
                print("no replies yet; theirs/ left empty")
            else:
                mine = orclient.our_group_ids(c, args.venue, args.number)
                written, skipped = orclient.store_replies(s, replies, mine)
                print(f"theirs/: {len(written)} new, {len(skipped)} unchanged")
            return 0
        except (orclient.ORError, FileNotFoundError, ValueError,
                ProvenanceError, pymupdf.FileNotFoundError,
                pymupdf.FileDataError) as e:
            # FileDataError: the download returned bytes that are not a PDF.
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "or-draft":
        from .llm import RetentionError
        from .openreview import fill as orfill
        from .openreview import form as orform
        try:
            s = Session(Path(args.session))
            form_path = s.dir / "form.json"
            if not form_path.exists():
                print("error: no form.json; run or-fetch --number first",
                      file=sys.stderr)
                return 2
            form = orform.from_json(form_path.read_text())
            style_path = (args.style or os.environ.get("REFEREEKIT_STYLE")
                          or str(_DEFAULT_STYLE))
            filled = orfill.fill(s, form, backend=_backend(),
                                 style_path=style_path,
                                 lengths=dict(x.split("=", 1) for x in args.length))
            s.our_draft("openreview.md").write_text(orfill.to_markdown(form, filled))
            s.our_draft("openreview.json").write_text(orfill.to_json(filled))
            print(f"openreview: {len(filled.values)} prose field(s) drafted, "
                  f"{len(filled.flags)} flag(s)")
            for f in filled.flags:
                print(f"  FLAG {f.kind} ({f.anchor}): {f.reason}")
            print("to fill in yourself:")
            for f in filled.blanks:
                span = (f"({f.enum[-1][0]}-{f.enum[0][0]})" if f.enum else f"({f.type})")
                print(f"  {f.name:<24} {span:<10} {f.description[:48]}")
            return 0
        except (FileNotFoundError, ValueError, RetentionError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.cmd == "or-responses":
        from .llm import RetentionError
        from .openreview import responses as orresponses
        try:
            s = Session(Path(args.session))
            received = [p.read_text() for p in sorted(s.theirs_dir.iterdir())
                        if p.is_file()]
            # Checked before constructing a backend: an empty theirs/ is an
            # input error, and it should not first fail on a missing API key.
            if not received:
                print("error: no received notes in theirs/; nothing to analyze",
                      file=sys.stderr)
                return 2
            ours = ""
            for name in ("openreview.md", "report.txt"):
                p = s.ours_dir / name
                if p.exists():
                    ours = p.read_text()
                    break
            text = orresponses.analyze(ours, received, backend=_backend())
            out = s.our_draft("response-analysis.txt")
            out.write_text(text)
            print(f"wrote {out} ({len(received)} received note(s))")
            return 0
        except (FileNotFoundError, ValueError, RetentionError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
```

- [ ] **Step 5: Import `ProvenanceError` in `cli.py`**

Change line 8 of `refereekit/cli.py`:

```python
from .session import Session, ProvenanceError
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli_openreview.py -v`
Expected: PASS, 13 tests.

- [ ] **Step 7: Confirm the CLI still imports without the extra installed**

Run: `.venv/bin/python -c "import refereekit.cli; print('ok')"`
Expected: `ok`. `openreview-py` is imported inside `make_client`, never at module scope.

Run: `grep -n "^from openreview\|^import openreview" refereekit/*.py refereekit/*/*.py`
Expected: no output. Every import of the third-party package is function-local.

- [ ] **Step 8: Add the README section**

In `README.md`, after the Phase 4 section (which ends at line 129 with the confidentiality note) and before `## What a PASS means`, add:

````markdown
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

    # draft the prose fields
    export REFEREEKIT_ZERO_RETENTION=1
    refereekit or-draft --session ./work/iclr-42 [--length summary=short]

    # summarize what the authors said back
    refereekit or-responses --session ./work/iclr-42

**Output:** `ours/openreview.md` for reading and pasting, `ours/openreview.json`
as a field-name-to-value mapping, and `ours/response-analysis.txt`.

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
````

- [ ] **Step 9: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: 225 passing: 150 existing plus 75 new (14 + 4 + 24 + 11 + 9 + 13).

- [ ] **Step 10: Verify the read-only constraint one more time**

Run: `grep -rn "post_note_edit\|put_attachment\|post_edge\|post_note" refereekit/`
Expected: no output.

- [ ] **Step 11: Commit**

```bash
git add refereekit/cli.py README.md tests/test_cli_openreview.py
git commit -m "feat: or-fetch, or-draft, or-responses

Listing assignments is a separate step from fetching one, so the referee
sees what they have before choosing, and listing touches no manuscript
content. Form and reply fetches are best-effort: before the review stage
opens there is no invitation and before the rebuttal period there are no
replies, and neither should cost the referee the pdf.

README documents that ratings are never filled and that venue LLM
policies differ and are not enforced here, with the NeurIPS prohibition
and the ICLR disclosure requirement quoted.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Manual verification against the live API

The suite is entirely offline, which is right for CI and leaves one thing
unproven: that the real client behaves as the fake claims. Run this once,
against a venue where you are a reviewer, before trusting the tool on a real
assignment.

```bash
export OPENREVIEW_USERNAME=... OPENREVIEW_PASSWORD=...
refereekit or-fetch --venue <your venue id> --session /tmp/or-smoke
```

Check, in order:

1. The assignment list matches what the OpenReview web UI shows you.
2. `refereekit or-fetch --venue <id> --number <N> --session /tmp/or-smoke-N`
   writes a `paper.pdf` that opens, and a `doc.json` whose page count matches.
3. `form.json` field names match the fields the web review form shows, in the
   same order.
4. `theirs/` holds what you expect and does **not** contain your own review.

Step 3 is the one that most repays checking. The fixtures are a published
default form and a synthetic ICLR-shaped one; a real venue may use a shape
neither anticipates. If `form.json` disagrees with the web form, save the
invitation JSON as a new fixture and extend `tests/test_or_form.py`.

`--baseurl https://devapi2.openreview.net` points at the API sandbox if you
want to try the calls without touching production.
