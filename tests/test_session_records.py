from refereekit.session import Session
from refereekit.types import Claim

def test_record_and_read_back_claims(tmp_path):
    s = Session.create(tmp_path, "p")
    s.record_claim(Claim("prescribed degree-size sequences", "quote", "1"))
    s.record_claim(Claim("counting identity", "equation", "3"))
    got = Session(s.dir).verified_claims()
    assert [c.anchor for c in got] == ["1", "3"]
    assert got[0].kind == "quote" and got[0].text.startswith("prescribed")
