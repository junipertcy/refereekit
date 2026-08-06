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
