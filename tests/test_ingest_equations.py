def test_inline_list_markers_are_not_equations():
    # UNIT TEST: inline (N) markers at left/center must be excluded,
    # but right-margin bare integers must be captured
    import fitz
    from refereekit.ingest import _extract_equation_numbers

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Inline markers at left margin (x ~ 72, well below 0.85*612 = 520.2)
    page.insert_text((72, 100), "if (1) they participate and (2) they share")
    # Right-margin equation label (x = 560 > 520.2)
    page.insert_text((560, 200), "3")
    # Bare integer at LEFT margin — ONLY geometry can reject this
    page.insert_text((72, 300), "7")

    eqs = _extract_equation_numbers(page)
    ids = {e.id for e in eqs}

    # Right-margin label must be captured
    assert "3" in ids, f"Expected '3' in {ids}"
    # Inline markers must NOT be captured (geometry excludes them)
    assert "1" not in ids, f"Inline '1' should not be in {ids}"
    assert "2" not in ids, f"Inline '2' should not be in {ids}"
    # Bare left-margin integer must be excluded by geometry
    assert "7" not in ids, f"bare left-margin '7' must be excluded by geometry, got {ids}"

    doc.close()

def test_real_paper_equations_best_effort_bound(real_doc):
    # best-effort: at least one plausible small equation label recovered
    small = [e for e in real_doc.equations if e.id.isdigit() and int(e.id) <= 12]
    assert len(small) >= 1

def test_no_figures_invented_by_equation_pass(real_doc):
    # equation pass must not corrupt figures (still exactly 1..4)
    assert sorted((f.id for f in real_doc.figures), key=int) == ["1", "2", "3", "4"]
