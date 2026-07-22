from refereekit.memory import SQLiteMemoryStore, Note

def test_store_then_recall_by_venue(tmp_path):
    m = SQLiteMemoryStore(tmp_path / "mem.db")
    m.store(Note(text="PRX: terse; reserve imperatives for real flaws", venue="PRX"))
    m.store(Note(text="PRE: fuller discussion ok", venue="PRE"))
    prx = m.recall("PRX")
    assert len(prx) == 1 and prx[0].venue == "PRX"
    assert m.recall("NATURE") == []
