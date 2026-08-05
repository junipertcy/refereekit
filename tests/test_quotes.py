from refereekit.quotes import quoted_spans, pair_with_pages, bare_page_anchors


def test_finds_a_straight_quote():
    prose = 'The estimator "dampens all residual couplings" per p. 7.'
    spans = quoted_spans(prose)
    assert len(spans) == 1
    start, end, text = spans[0]
    assert text == "dampens all residual couplings"
    assert prose[start:end] == text


def test_finds_a_curly_quote():
    prose = 'The estimator “dampens all residual couplings” per p. 7.'
    assert [t for _, _, t in quoted_spans(prose)] == ["dampens all residual couplings"]


def test_ignores_very_short_quotes():
    """A two-character quote is jargon or scare-quoting, not evidence."""
    assert quoted_spans('They call it "ok" on p. 3.') == []


def test_no_quotes_returns_empty():
    assert quoted_spans("Plain prose citing p. 3 with no quotation.") == []


def test_pairs_quote_with_following_page():
    prose = 'It "dampens all residual couplings in that regime" on p. 7.'
    assert pair_with_pages(prose) == [("dampens all residual couplings in that regime", "7")]


def test_pairs_quote_with_preceding_page():
    prose = 'On p. 7 the authors write "dampens all residual couplings in that regime".'
    assert pair_with_pages(prose) == [("dampens all residual couplings in that regime", "7")]


def test_picks_the_nearer_page_anchor():
    prose = ('On p. 3 nothing happens. The text "dampens all residual couplings" '
             'appears on p. 7 instead.')
    assert pair_with_pages(prose) == [("dampens all residual couplings", "7")]


def test_quote_with_no_page_anchor_is_dropped():
    """Nothing to check it against, so it is not a claim."""
    assert pair_with_pages('They write "dampens all residual couplings" somewhere.') == []


def test_two_quotes_two_pages():
    prose = 'First "the lower band remains order one" on p. 3. Then "a spectral plateau of width W" on p. 7.'
    assert pair_with_pages(prose) == [
        ("the lower band remains order one", "3"),
        ("a spectral plateau of width W", "7"),
    ]


def test_offsets_bound_the_stripped_text():
    """The returned offsets must slice out exactly the returned text,
    even when the quotation carries surrounding whitespace."""
    prose = 'The bound "  dampens all residual couplings  " holds on p. 7.'
    spans = quoted_spans(prose)
    assert len(spans) == 1
    start, end, text = spans[0]
    assert text == "dampens all residual couplings"
    assert prose[start:end] == text


def test_bare_page_anchors_single_quoted_page():
    """One quotation paired to the only page anchor leaves no bare claims."""
    prose = 'The estimator "dampens all residual couplings in that regime" on p. 7.'
    assert bare_page_anchors(prose) == []


def test_bare_page_anchors_quoted_and_bare_same_page():
    """A quotation claims one page mention, the second mention is bare."""
    prose = 'The estimator "dampens all residual couplings in that regime" on p. 7. See also p. 7.'
    assert bare_page_anchors(prose) == ['7']


def test_bare_page_anchors_two_quotes_one_anchor():
    """Two quotations both claim the same anchor, no bare mention."""
    prose = 'It "dampens all residual couplings" on p. 7 and "the lower band remains order one" on p. 7.'
    assert bare_page_anchors(prose) == []


def test_bare_page_anchors_page_inside_quotation():
    """A page number inside a quotation is not claimed by any quote, surfaces as bare."""
    prose = 'They write "as shown on p. 7 the bound holds" on p. 9.'
    assert bare_page_anchors(prose) == ['9']


def test_bare_page_anchors_negative_count_regression():
    """Three quotations to one anchor plus one bare mention: the old Counter
    approach computed bare_count = 2 - 3 = -1, range(-1) yielded nothing, and
    the bare pointer vanished."""
    prose = 'Note "dampens all residual couplings", "the lower band remains order one", "a spectral plateau of width W" on p. 7. Also p. 7.'
    assert bare_page_anchors(prose) == ['7']


def test_bare_page_anchors_two_quotes_one_anchor_plus_bare():
    """Two quotations to one anchor plus one bare mention."""
    prose = 'They say "dampens all residual couplings" and "the lower band remains order one" on p. 7. See also p. 7.'
    assert bare_page_anchors(prose) == ['7']


def test_bare_page_anchors_no_quotes_only():
    """Bare page pointer with no quotations anywhere."""
    prose = 'The spike eigenvalue is order P, see p. 7.'
    assert bare_page_anchors(prose) == ['7']


def test_bare_page_anchors_no_pages():
    """No page anchors at all."""
    assert bare_page_anchors('As Eq. (25) shows.') == []


def test_bare_page_anchors_quote_with_no_page():
    """Quotation with no page anchor anywhere is not paired, so no anchors are claimed."""
    prose = 'They call it "dampens all residual couplings" without a page.'
    assert bare_page_anchors(prose) == []


def test_bare_page_anchors_multiple_bare_only():
    """Multiple bare page references, no quotations."""
    prose = 'See p. 3 and p. 9 for details.'
    assert bare_page_anchors(prose) == ['3', '9']


def test_short_quotes_do_not_invert_parity():
    """Regression: short quotes (<12 chars) below the floor cannot match, so
    the regex engine resumes inside them and pairs their close with the next
    open, yielding the text BETWEEN quotations as a false quotation."""
    prose = 'The bound is "tight" and the kernel "dampens all residual couplings in that regime" on p. 7.'
    spans = quoted_spans(prose)
    # Should return only the long genuine quotation, not the inter-quote prose
    assert len(spans) == 1
    assert spans[0][2] == "dampens all residual couplings in that regime"
    # The false artifact 'and the kernel' must NOT appear
    assert not any("and the kernel" in text for _, _, text in spans)


def test_alternating_short_and_long_quotes():
    """Only long quotations (≥12 chars) should be returned; short ones are
    scare-quoting and must not break parity for subsequent quotes."""
    prose = 'They call it "ok" but the model "shows convergence behavior" and "no" again.'
    spans = quoted_spans(prose)
    texts = [t for _, _, t in spans]
    # Only the long quote survives
    assert texts == ["shows convergence behavior"]
    # Short quotes are not returned
    assert "ok" not in texts
    assert "no" not in texts
