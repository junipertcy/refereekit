import json
from pathlib import Path
from .types import Document, Claim
from .ingest import to_json, from_json


class ProvenanceError(RuntimeError):
    """Raised on an attempt to overwrite a received document."""


class Session:
    def __init__(self, dir: Path):
        self.dir = Path(dir)
        self.doc_json = self.dir / "doc.json"
        self.html = self.dir / "index.html"
        self.state_json = self.dir / "state.json"

    @classmethod
    def create(cls, base, name: str) -> "Session":
        d = Path(base) / name
        d.mkdir(parents=True, exist_ok=True)
        return cls(d)

    def save_doc(self, doc: Document) -> None:
        self.doc_json.write_text(to_json(doc))

    def load_doc(self) -> Document:
        return from_json(self.doc_json.read_text())

    def _state(self) -> dict:
        if self.state_json.exists():
            return json.loads(self.state_json.read_text())
        return {}

    def set_state(self, key, value) -> None:
        s = self._state(); s[key] = value
        self.state_json.write_text(json.dumps(s))

    def get_state(self, key, default=None):
        return self._state().get(key, default)

    def record_claim(self, claim: Claim) -> None:
        claims = self.get_state("claims", [])
        claims.append({"text": claim.text, "kind": claim.kind, "anchor": claim.anchor})
        self.set_state("claims", claims)

    def verified_claims(self) -> list[Claim]:
        return [Claim(**c) for c in self.get_state("claims", [])]

    @property
    def ours_dir(self) -> Path:
        """Documents this referee wrote. Drafts, safe to regenerate."""
        d = self.dir / "ours"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def theirs_dir(self) -> Path:
        """Documents received from others: co-referee reports, editor letters.
        Authoritative, never generated here."""
        d = self.dir / "theirs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def our_draft(self, name: str) -> Path:
        """Path for one of our own drafts."""
        return self.ours_dir / name

    def put_theirs(self, name: str, content: str) -> Path:
        """Store a received document. Write-once: a received artifact that can
        be silently replaced is indistinguishable from one we generated."""
        p = self.theirs_dir / name
        if p.exists():
            raise ProvenanceError(
                f"{p} already exists; received documents are write-once")
        p.write_text(content)
        return p
