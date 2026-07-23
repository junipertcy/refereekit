import pytest
from refereekit.memory import SQLiteMemoryStore, Note
from refereekit.guard import ManuscriptLeakError

def test_store_requires_doc(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    with pytest.raises(ValueError):
        m.store(Note("PRX: terse", "PRX"), None)   # no doc -> fail closed

def test_store_then_recall_by_venue(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    m.store(Note("PRX: terse; reserve imperatives for real flaws", "PRX"), real_doc,
            created_at="2026-01-01T00:00:00")
    m.store(Note("PRE: fuller discussion ok", "PRE"), real_doc,
            created_at="2026-01-02T00:00:00")
    prx = m.recall("PRX")
    assert len(prx) == 1 and prx[0].venue == "PRX"
    assert m.recall("NATURE") == []

def test_store_rejects_manuscript_text(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    with pytest.raises(ManuscriptLeakError):
        m.store(Note("prescribed degree-size sequences", "PRX"), real_doc)
