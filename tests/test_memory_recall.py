from refereekit.memory import SQLiteMemoryStore, Note

def test_recall_dedup_recency_cap(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    # duplicate text (older + newer) + a distinct newer note
    m.store(Note("dup note", "PRX"), real_doc, created_at="2026-01-01T00:00:00")
    m.store(Note("dup note", "PRX"), real_doc, created_at="2026-01-05T00:00:00")
    m.store(Note("newer distinct", "PRX"), real_doc, created_at="2026-01-09T00:00:00")
    got = m.recall("PRX")
    texts = [n.text for n in got]
    assert texts == ["newer distinct", "dup note"]   # distinct, newest-first
    assert len(got) == 2

def test_recall_respects_limit(tmp_path, real_doc):
    m = SQLiteMemoryStore(tmp_path / "m.db")
    for i in range(25):
        m.store(Note(f"note {i}", "PRX"), real_doc, created_at=f"2026-02-{i+1:02d}T00:00:00")
    assert len(m.recall("PRX", limit=10)) == 10
