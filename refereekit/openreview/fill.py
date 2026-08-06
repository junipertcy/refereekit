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


def validate_lengths(form, lengths) -> None:
    """A --length naming no field on this form is a typo, or a form that
    differs from the one the referee expected. Both are worth hearing about.

    Exposed so cli.py can check before constructing a backend: with the llm
    extra absent, checking inside fill() reported a broken install when the
    real problem was a typo in the flag. One implementation, so the CLI and
    fill cannot disagree about what counts as a valid name.
    """
    unknown = sorted(set(lengths or {}) - {f.name for f in form.fields})
    if unknown:
        raise ValueError(
            f"--length names no field in this form: {', '.join(unknown)}")


def validate_pool(session) -> None:
    """Refuse to draft from a session that has been fetched but not reviewed.

    or-fetch records the venue, the number and the forum; claims and the
    verdict come from the review loop. Drafting without one sends the model no
    verified quotation and no verdict, so every field would be invented while
    the command reported success. That inverts the discipline the rest of the
    package exists to enforce, so it is refused rather than flagged: an empty
    pool is an input error, not a citation problem.

    Exposed so cli.py can check before constructing a backend, and called by
    fill so the rule holds however fill is reached.
    """
    pool = drafts.build_pool(session)
    if pool["claims"] or pool["verdict"]:
        return
    raise ValueError(
        f"no verified claims in this session; run refereekit review "
        f"{session.dir / 'paper.pdf'} --session {session.dir} first")


def fill(session, form, *, backend, style_path, lengths=None,
         memory=None, venue=None) -> FilledForm:
    """One backend call per prose field.

    Per-field calls, rather than one call for the whole form, so each field
    gets the venue's own instruction and so a field that fails does not lose
    the others.
    """
    lengths = dict(lengths or {})
    validate_lengths(form, lengths)
    validate_pool(session)
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
