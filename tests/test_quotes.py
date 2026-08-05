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
    prose = 'The bound is "tight" whereas the estimator "dampens all residual couplings in that regime" on p. 7.'
    spans = quoted_spans(prose)
    # Should return only the long genuine quotation, not the inter-quote prose
    assert len(spans) == 1
    assert spans[0][2] == "dampens all residual couplings in that regime"
    # The false artifact 'whereas the estimator' must NOT appear
    assert not any("whereas the estimator" in text for _, _, text in spans)


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


def test_nearest_prefers_preceding_anchor_misattribution_case():
    """Regression: _nearest chose the nearest anchor in either direction,
    canceling detection of misattributions. When prose cites p. 15 but the
    quotation is from p. 7, and both anchors exist, the tool must attribute
    to the anchor the prose actually wrote (p. 15), not re-attribute to p. 7."""
    # Genuine p.7 quote but prose claims p. 15, with cf. p. 7 afterward
    prose = 'The authors assert on p. 15 that the model "shows convergence to equilibrium quickly" (cf. p. 7).'
    assert pair_with_pages(prose) == [("shows convergence to equilibrium quickly", "15")]


def test_nearest_prefers_preceding_anchor_correct_order_case():
    """When the quotation IS correctly attributed to an earlier page, that
    attribution must be preserved even if a later page anchor is closer."""
    prose = 'Page 7 says "shows convergence to equilibrium quickly"; page 15 shows the panels.'
    assert pair_with_pages(prose) == [("shows convergence to equilibrium quickly", "7")]


def test_nearest_fallback_to_following_anchor():
    """When NO anchor precedes the quotation, fall back to the closest
    following anchor. This is the common form: quote comes before its citation."""
    prose = 'The estimator "shows convergence to equilibrium quickly" on p. 7.'
    assert pair_with_pages(prose) == [("shows convergence to equilibrium quickly", "7")]


def test_nearest_inside_span_wins():
    """An anchor inside the quoted span has distance 0 and wins."""
    prose = 'They write "as shown on p. 7 the bound holds" on p. 9.'
    # p. 7 is inside the span, p. 9 follows it: p. 7 wins (distance 0)
    assert pair_with_pages(prose) == [("as shown on p. 7 the bound holds", "7")]


def test_nearest_two_quotes_same_page():
    """Two quotations both attributed to p. 7 stay attributed to p. 7."""
    prose = 'It "shows convergence to equilibrium quickly" on p. 7 and "demonstrates stability properties" on p. 7.'
    assert pair_with_pages(prose) == [
        ("shows convergence to equilibrium quickly", "7"),
        ("demonstrates stability properties", "7"),
    ]


def test_attribution_keeps_the_page_the_prose_named():
    """Pins that a misattributed quotation stays attributed to the page the
    prose named, so the verifier can report the mismatch instead of hiding it."""
    prose = ('The authors assert on p. 15 that the model '
             '"dampens all residual couplings" (cf. p. 7).')
    assert pair_with_pages(prose) == [("dampens all residual couplings", "15")]
    assert bare_page_anchors(prose) == ["7"]


def test_attribution_not_stolen_by_a_following_citation():
    """Pins that a following page citation does not steal a quotation from the
    citation that introduced it."""
    prose = 'Page 7 says "dampens all residual couplings"; page 15 shows the panels.'
    assert pair_with_pages(prose) == [("dampens all residual couplings", "7")]
    assert bare_page_anchors(prose) == ["15"]


def test_attribution_falls_back_to_the_following_citation():
    prose = 'The estimator "dampens all residual couplings" on p. 7.'
    assert pair_with_pages(prose) == [("dampens all residual couplings", "7")]
    assert bare_page_anchors(prose) == []


def test_attribution_prefers_a_citation_inside_the_quotation():
    prose = 'They write "as shown on p. 7 the bound holds" on p. 9.'
    assert pair_with_pages(prose) == [("as shown on p. 7 the bound holds", "7")]
    assert bare_page_anchors(prose) == ["9"]


def test_attribution_two_quotes_two_mentions_of_one_page():
    prose = ('It "dampens all residual couplings" on p. 7 '
             'and "the lower band remains order one" on p. 7.')
    assert pair_with_pages(prose) == [
        ("dampens all residual couplings", "7"),
        ("the lower band remains order one", "7"),
    ]
    assert bare_page_anchors(prose) == []


def test_a_sentence_final_ordinary_word_is_not_an_abbreviation():
    """Regression: "no" and "refs" were listed as abbreviations, so a sentence
    ending in one was not split and the previous sentence's citation stayed in
    scope. Neither word can precede a page anchor, so they protected nothing."""
    prose = ('On p. 15 the answer is no. The text '
             '"dampens all residual couplings" appears on p. 7 instead.')
    assert pair_with_pages(prose) == [("dampens all residual couplings", "7")]
    assert bare_page_anchors(prose) == ["15"]


def test_a_contrast_citation_does_not_steal_a_shared_quotation():
    """Regression: exclusivity was applied to following citations too, so the
    second quotation was pushed onto a page it quotes nothing from. Both
    quotations belong to p. 7; p. 15 is a contrast and stays bare."""
    prose = ('Both "dampens all residual couplings" and '
             '"the lower band remains order one" appear on p. 7, unlike p. 15.')
    assert pair_with_pages(prose) == [
        ("dampens all residual couplings", "7"),
        ("the lower band remains order one", "7"),
    ]
    assert bare_page_anchors(prose) == ["15"]
