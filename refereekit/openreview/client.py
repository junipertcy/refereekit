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
    """Our own profile id, which login already established.

    Read from the client rather than fetched. get_profile() takes an email or
    an id and looks that up; with no argument openreview-py v2 sends an empty
    query and the API answers 400 "request must NOT have fewer than 1
    properties", so the v1 idiom of calling it bare to learn who we are fails
    against every venue. The same v1/v2 drift already caught get_attachment.
    """
    got = getattr(getattr(client, "profile", None), "id", None)
    if not got:
        raise ORError(
            "could not read your openreview profile from the login response")
    return got


def list_assignments(client, venue: str) -> tuple:
    """Assignments are edges from the reviewer's profile to the submission.

    Returns (assignments, unreadable head ids). An edge gives head (the
    submission id) but neither number nor title, so each head is resolved to
    print a list the referee can act on.

    One head that will not resolve, a withdrawn or desk-rejected paper still
    carrying an assignment edge being the usual cause, used to lose the whole
    list. Listing is the entry point to this feature, so the unreadable head is
    skipped and named and the rest is returned.
    """
    me = profile_id(client)
    try:
        edges = client.get_all_edges(
            invitation=f"{venue}/Reviewers/-/Assignment", tail=me)
    except Exception as e:
        raise ORError(
            f"no venue {venue}; check the venue id, "
            f"e.g. ICLR.cc/2027/Conference") from e
    out, unreadable = [], []
    for edge in edges:
        try:
            note = client.get_note(edge.head)
        except Exception:
            unreadable.append(edge.head)
            continue
        out.append(Assignment(number=note.number, forum=note.id,
                              title=_content_value(note, "title")))
    out.sort(key=lambda a: a.number)
    return out, unreadable


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


def _reason(e: Exception) -> str:
    """An exception message, safe to print.

    A failure here can be an auth failure, and openreview's own exceptions have
    echoed request parameters before, so the credentials are redacted out of the
    text rather than trusted not to appear in it. Credentials come from the
    environment only, so this is the whole set of values to remove.
    """
    text = str(e) or e.__class__.__name__
    for var in ("OPENREVIEW_PASSWORD", "OPENREVIEW_USERNAME"):
        secret = os.environ.get(var)
        if secret:
            text = text.replace(secret, f"<{var}>")
    return text


def fetch_form(client, venue: str, number: int) -> tuple:
    """Returns (form or None, reason it is None).

    None when the review stage has not opened yet, which is not an error. It is
    also None when the lookup failed, which is a different thing entirely: a
    503 or an expired token reported as "the review stage has not opened" sent
    the referee to run the or-fetch they had just run. The reason distinguishes
    the two, so the caller can say which happened.
    """
    inv_id = f"{venue}/Submission{number}/-/Official_Review"
    try:
        inv = client.get_invitation(inv_id)
    except Exception as e:
        return None, _reason(e) or "no reason given"
    edit = inv.get("edit") if isinstance(inv, dict) else getattr(inv, "edit", None)
    return parse_form({"id": inv_id, "edit": edit or {}}), ""


def our_group_ids(client, venue: str, number: int) -> set | None:
    """Our own anonymous reviewer group ids for this submission.

    A reply signed by one of these is ours, not theirs. None means the lookup
    itself failed and ownership could not be established; an empty set means it
    succeeded and matched nothing, which a venue naming its groups Reviewers,
    AnonReviewer1 or Anonymous_Reviewer also produces. Both leave ownership
    unverifiable, so store_replies treats them alike, but only the first is a
    fault, and collapsing them into one value hid that from the caller.
    """
    try:
        groups = client.get_groups(
            prefix=f"{venue}/Submission{number}/Reviewer_",
            signatory=profile_id(client))
    except Exception:
        return None
    return {g.id for g in groups}


def fetch_replies(client, forum: str) -> tuple:
    """Every reply on the submission's forum: co-reviewers' official reviews,
    author comments, and our own review once posted.

    Returns (replies, reason the list is empty). Best-effort, like fetch_form
    and our_group_ids: raising here exited 2 after paper.pdf, doc.json,
    form.json and state.json were already on disk, and the pdf is the part the
    referee needs first.
    """
    try:
        notes = client.get_all_notes(forum=forum, details="replies")
    except Exception as e:
        return [], _reason(e)
    replies = []
    for n in notes:
        details = getattr(n, "details", None) or {}
        replies.extend(details.get("replies") or [])
    return replies, ""


def _safe(s) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(s))


def _epoch_ms(tcdate, note_id: str = "unknown") -> int | None:
    """OpenReview's own creation time, epoch milliseconds, validated.

    A non-integer reached int() unsanitized while the note id went through
    _safe, and the resulting bare 'invalid literal for int()' meant nothing to
    a referee. None for an absent timestamp, which is not an error.
    """
    if not tcdate:
        return None
    try:
        return int(tcdate)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"reply {_safe(note_id)} has a tcdate that is not epoch "
            f"milliseconds: {_safe(tcdate)}") from e


def _iso(tcdate) -> str:
    """OpenReview's own creation time, epoch milliseconds. This reads no local
    clock, so a re-fetch produces the same filename and the same header."""
    ms = _epoch_ms(tcdate)
    if ms is None:
        return "unknown"
    return datetime.datetime.fromtimestamp(
        ms / 1000, tz=datetime.timezone.utc).isoformat()


def _render_reply(r: dict) -> str:
    sigs = ", ".join(r.get("signatures") or []) or "unknown"
    inv = ", ".join(r.get("invitations") or []) or "unknown"
    body = []
    for k, v in (r.get("content") or {}).items():
        body.append(f"{k}: {v.get('value') if isinstance(v, dict) else v}")
    return (f"# openreview note {r.get('id', 'unknown')} by {sigs} "
            f"at {_iso(r.get('tcdate'))}\n"
            f"# invitation: {inv}\n\n" + "\n\n".join(body) + "\n")


def _ownership_unverified(r: dict) -> bool:
    """Could this reply be our own review, with no skip set to rule it out?

    Only an Official_Review is a candidate: an author comment or a meta-review
    is not something we could have written, so an unusable skip set must not
    quarantine the whole discussion. A ~-prefixed signature is a named profile
    rather than one of our anonymous reviewer groups, so a venue with
    non-anonymous reviewing still receives its co-reviewers' reports.
    """
    if not any("Official_Review" in inv for inv in (r.get("invitations") or [])):
        return False
    sigs = r.get("signatures") or []
    return not sigs or not all(str(s).startswith("~") for s in sigs)


def store_replies(session, replies: list, skip_signatures) -> tuple:
    """Write received notes to theirs/. Returns (written, skipped, held) names.

    Named <note-id>-<tcdate>.txt. A rebuttal revised during the discussion
    period has a new tcdate and so becomes a new file: both versions are kept
    and the change is visible. That keeps put_theirs write-once rather than
    working around it. An identical re-fetch produces a name that already
    exists, which put_theirs would reject, so it is skipped instead.

    A reply signed by one of our own anonymous reviewer groups is ours, not
    theirs. Storing it here would recreate the confusion between our draft and
    someone else's report that ours/ and theirs/ exist to prevent.

    When skip_signatures is empty or None, ownership could not be established,
    and a single hardcoded group prefix was never a sufficient test anyway. An
    Official_Review is then held back rather than written: theirs/ is read
    wholesale by or-responses and fed to the model as what came back from
    others, so a wrong guess there analyzes our own review against itself. The
    caller names the held-back notes so the referee can check them by hand.
    """
    ownership_known = bool(skip_signatures)
    skip = set(skip_signatures or ())
    written, skipped, held = [], [], []
    for r in replies:
        if any(s in skip for s in (r.get("signatures") or [])):
            continue
        note_id = r.get("id", "unknown")
        # Validated for the message and sanitized for the name: both halves go
        # through _safe, so neither can steer the write out of theirs/.
        stamp = _epoch_ms(r.get("tcdate"), note_id) or 0
        name = f"{_safe(note_id)}-{_safe(stamp)}.txt"
        if not ownership_known and _ownership_unverified(r):
            held.append(name)
            continue
        if (session.theirs_dir / name).exists():
            skipped.append(name)
            continue
        session.put_theirs(name, _render_reply(r))
        written.append(name)
    return written, skipped, held
