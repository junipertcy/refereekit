import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

@dataclass
class Note:
    text: str
    venue: str
    kind: str = "style"

class MemoryStore(Protocol):
    def recall(self, venue: str) -> list["Note"]: ...
    def store(self, note: "Note") -> None: ...

class SQLiteMemoryStore:
    def __init__(self, path):
        self.path = str(path)
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS notes (text TEXT, venue TEXT, kind TEXT)")

    def store(self, note: Note) -> None:
        with sqlite3.connect(self.path) as c:
            c.execute("INSERT INTO notes (text, venue, kind) VALUES (?,?,?)",
                      (note.text, note.venue, note.kind))

    def recall(self, venue: str) -> list[Note]:
        with sqlite3.connect(self.path) as c:
            rows = c.execute("SELECT text, venue, kind FROM notes WHERE venue=?",
                             (venue,)).fetchall()
        return [Note(text=t, venue=v, kind=k) for (t, v, k) in rows]
