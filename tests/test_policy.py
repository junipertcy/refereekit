"""Venue policy: which venues forbid sending the manuscript to an outside LLM.

Today this rule lives in a comment in .env.template and in the referee's head,
and the control is "remember not to set REFEREEKIT_ZERO_RETENTION". One shell
that reviewed a journal paper an hour ago still has it set, and the next command
is a NeurIPS assignment. The venue is already known at that point, so the tool
can refuse instead of relying on the referee remembering.
"""
import pytest

from refereekit.policy import VenuePolicyError, assert_llm_permitted, llm_permitted


def test_a_prohibited_venue_refuses():
    with pytest.raises(VenuePolicyError, match="NeurIPS"):
        assert_llm_permitted("NeurIPS")


def test_an_openreview_venue_id_matches_the_same_rule():
    """or-fetch hands back ids like 'NeurIPS.cc/2026/Conference', not bare names."""
    with pytest.raises(VenuePolicyError):
        assert_llm_permitted("NeurIPS.cc/2026/Conference")


def test_matching_ignores_case_and_spacing():
    with pytest.raises(VenuePolicyError):
        assert_llm_permitted("neurips 2026")


def test_an_unlisted_venue_is_permitted():
    """Default is permit: code cannot know every venue's policy, and refusing
    the unknown would make the tool unusable for every journal."""
    assert llm_permitted("PRX") is True
    assert_llm_permitted("PRX")


def test_no_venue_is_permitted():
    """Not every run names a venue; absence is not a prohibition."""
    assert_llm_permitted(None)
    assert_llm_permitted("")


def test_an_override_file_can_add_a_venue(tmp_path, monkeypatch):
    """Policy is the referee's to state, so the table must be extendable."""
    p = tmp_path / "policy.toml"
    p.write_text('[venues]\n"Some Journal" = { llm = false }\n')
    monkeypatch.setenv("REFEREEKIT_VENUE_POLICY", str(p))
    with pytest.raises(VenuePolicyError, match="Some Journal"):
        assert_llm_permitted("Some Journal")


def test_an_override_file_can_permit_a_built_in_prohibition(tmp_path, monkeypatch):
    """If a venue changes its rules, the referee must not have to patch the package."""
    p = tmp_path / "policy.toml"
    p.write_text('[venues]\nNeurIPS = { llm = true }\n')
    monkeypatch.setenv("REFEREEKIT_VENUE_POLICY", str(p))
    assert_llm_permitted("NeurIPS")


def test_the_error_says_what_to_do():
    """A refusal that does not name the rule reads as a bug, not a policy."""
    with pytest.raises(VenuePolicyError) as e:
        assert_llm_permitted("NeurIPS")
    msg = str(e.value)
    assert "REFEREEKIT_VENUE_POLICY" in msg
