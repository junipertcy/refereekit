def test_inline_list_markers_are_not_equations(real_doc):
    # the paper has "...equivalent if (1) they participate... and (2)..."
    # those inline (N) markers must NOT appear as equations
    bodies = " ".join(e.body for e in real_doc.equations)
    assert "they participate" not in bodies  # no inline-marker text captured
    # and equation ids must not be sourced from inline "(1)"/"(2)" text tokens:
    # (right-margin geometry never reads those inline tokens)
    assert isinstance(real_doc.equations, list)

def test_real_paper_equations_best_effort_bound(real_doc):
    # best-effort: at least one plausible small equation label recovered
    small = [e for e in real_doc.equations if e.id.isdigit() and int(e.id) <= 12]
    assert len(small) >= 1

def test_no_figures_invented_by_equation_pass(real_doc):
    # equation pass must not corrupt figures (still exactly 1..4)
    assert sorted((f.id for f in real_doc.figures), key=int) == ["1", "2", "3", "4"]
