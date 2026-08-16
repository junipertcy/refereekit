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
        # A Profile object, not a bare id: the real client builds one during
        # login, and code that reads client.profile.id must fail here when it
        # would fail against the API.
        self.profile = FakeProfile(id=profile)
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

    def get_profile(self, email_or_id=None):
        """A lookup, not "my profile". openreview-py v2 builds an empty query
        when called with no argument and the API rejects it with a 400
        ValidationError, so the no-arg call is an error here too rather than a
        convenient way to learn who we are."""
        self._log("get_profile", email_or_id=email_or_id)
        if not email_or_id:
            raise Boom("request must NOT have fewer than 1 properties")
        return FakeProfile(id=email_or_id)

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
        # The discussion query and the submission query share one method, so
        # each logs under its own name: raise_on needs to fail one without the
        # other, since a test for a broken discussion endpoint still has to
        # fetch the submission first.
        if kw.get("forum"):
            self._log("get_all_notes/forum", **kw)
            return [FakeNote(id=kw["forum"],
                             details={"replies": list(self._replies)})]
        self._log("get_all_notes", **kw)
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
