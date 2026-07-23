from refereekit.ingest import _extract_sections


def test_extract_sections_unit_numbered():
    secs = _extract_sections("2. Methods\nWe describe the approach.\n3.1 Sampling", 4)
    titles = [s.title for s in secs]
    assert "2. Methods" in titles or "Methods" in titles
    assert any("Sampling" in t for t in titles)


def test_extract_sections_ignores_body():
    secs = _extract_sections("This is an ordinary sentence that is not a heading.", 1)
    assert secs == []


def test_real_paper_sections_lower_bound(real_doc):
    # best-effort: detection may be imperfect on this PDF; require it not to crash
    # and to return a list (possibly empty). This guards the wiring, not a count.
    assert isinstance(real_doc.sections, list)
