# tests/test_render.py
from refereekit.render import init_page, append_qa, pick_port
from refereekit.session import Session

def test_append_prepends_numbered_cards(tmp_path):
    s = Session.create(tmp_path, "p")
    init_page(s, "Test")
    append_qa(s, "first?", "<p>one</p>")
    append_qa(s, "second?", "<p>two</p>")
    html = s.html.read_text()
    assert "MathJax" in html
    assert html.index("#2") < html.index("#1")   # newest on top
    assert "first?" in html and "second?" in html

def test_pick_port_returns_int():
    assert isinstance(pick_port(8888), int)
