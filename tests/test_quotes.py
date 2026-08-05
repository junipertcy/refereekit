from refereekit.quotes import quoted_spans, pair_with_pages


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
