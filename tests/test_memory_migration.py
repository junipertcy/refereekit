import sqlite3
from refereekit.memory import SQLiteMemoryStore, Note


def test_opens_and_migrates_old_schema(tmp_path):
    db = tmp_path / "old.db"
    # simulate an SP-B-era DB with no created_at
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE notes (text TEXT, venue TEXT, kind TEXT)")
        c.execute("INSERT INTO notes VALUES ('old note','PRX','style')")
    m = SQLiteMemoryStore(db)  # must migrate, not crash
    cols = _columns(db)
    assert "created_at" in cols


def test_fresh_db_has_created_at(tmp_path):
    m = SQLiteMemoryStore(tmp_path / "new.db")
    assert "created_at" in _columns(tmp_path / "new.db")


def _columns(db):
    with sqlite3.connect(db) as c:
        return {r[1] for r in c.execute("PRAGMA table_info(notes)")}
