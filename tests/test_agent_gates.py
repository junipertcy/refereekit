from refereekit.agent.loop import _verdict_gate, _detail_gate, _editor_answers
from refereekit.session import Session

def test_verdict_gate_records_state(tmp_path):
    s = Session.create(tmp_path, "p")
    script = iter(["major revision", "PRX", "major"])
    v = _verdict_gate(s, input_fn=lambda _="": next(script), output_fn=lambda _:None)
    assert v["recommend"] == "major revision" and v["venue"] == "PRX"
    assert Session(s.dir).get_state("verdict")["venue"] == "PRX"

def test_detail_gate_parses_lengths():
    script = iter(["major=short, minor=medium"])
    d = _detail_gate(input_fn=lambda _="": next(script))
    assert d == {"major": "short", "minor": "medium"}

def test_detail_gate_blank_is_default():
    assert _detail_gate(input_fn=lambda _="": "") == {}
