def test_real_paper_figures_exact(real_doc):
    ids = sorted((f.id for f in real_doc.figures), key=int)
    assert ids == ["1", "2", "3", "4"]

def test_figure_caption_captured(real_doc):
    fig1 = next(f for f in real_doc.figures if f.id == "1")
    assert fig1.caption.startswith("(a) Geometric representation")

def test_extract_figures_unit():
    from refereekit.ingest import _extract_figures
    figs = _extract_figures("FIG. 7. (a) example caption here.\nother text", 5)
    assert len(figs) == 1 and figs[0].id == "7" and figs[0].page == 5
    assert figs[0].caption.startswith("(a) example")

def test_extract_figures_handles_figure_prefix():
    from refereekit.ingest import _extract_figures
    figs = _extract_figures("Figure 2. a caption", 1)
    assert len(figs) == 1 and figs[0].id == "2"
