import os
import sqlite3
from dataclasses import dataclass
from typing import Protocol
from datetime import datetime, timezone
from .guard import assert_no_manuscript

@dataclass
class Note:
    text: str
    venue: str
    kind: str = "style"
    created_at: str | None = None

class MemoryStore(Protocol):
    def recall(self, venue: str, limit: int = 20) -> list["Note"]: ...
    def store(self, note: "Note", doc, *, created_at: str | None = None) -> None: ...

class SQLiteMemoryStore:
    def __init__(self, path: str | os.PathLike):
        self.path = str(path)
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS notes (text TEXT, venue TEXT, kind TEXT, created_at TEXT)")
            cols = {r[1] for r in c.execute("PRAGMA table_info(notes)")}
            if "created_at" not in cols:
                c.execute("ALTER TABLE notes ADD COLUMN created_at TEXT")

    def store(self, note: Note, doc, *, created_at: str | None = None) -> None:
        if doc is None:
            raise ValueError("store requires the session Document")
        assert_no_manuscript(note.text, doc)
        ts = created_at or note.created_at or datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as c:
            c.execute("INSERT INTO notes (text, venue, kind, created_at) VALUES (?,?,?,?)",
                      (note.text, note.venue, note.kind, ts))

    def recall(self, venue: str, limit: int = 20) -> list[Note]:
        with sqlite3.connect(self.path) as c:
            rows = c.execute(
                "SELECT text, kind, MAX(created_at) AS ca FROM notes "
                "WHERE venue=? GROUP BY text ORDER BY ca DESC LIMIT ?",
                (venue, limit),
            ).fetchall()
        return [Note(text=t, venue=venue, kind=k, created_at=ca) for (t, k, ca) in rows]
