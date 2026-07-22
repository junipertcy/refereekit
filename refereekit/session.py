import json
from pathlib import Path
from .types import Document
from .ingest import to_json, from_json

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
