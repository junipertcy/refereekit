"""Backend selection: which transport `_backend()` builds, and what it attests.

The transport is chosen by environment because the choice is a property of the
machine and account the referee is sitting at, not of the paper under review.
"""
import pytest

from refereekit.cli import _backend
from refereekit.llm import AnthropicBackend, BedrockBackend, FakeBackend


def test_bedrock_selected_by_env(monkeypatch):
    monkeypatch.setenv("REFEREEKIT_BACKEND", "bedrock")
    monkeypatch.setenv("REFEREEKIT_ZERO_RETENTION", "1")
    assert isinstance(_backend(), BedrockBackend)


def test_anthropic_is_the_default(monkeypatch):
    monkeypatch.delenv("REFEREEKIT_BACKEND", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    assert isinstance(_backend(), AnthropicBackend)


def test_fake_wins_over_a_configured_transport(monkeypatch):
    """Offline mode must not be defeated by a leftover transport setting."""
    monkeypatch.setenv("REFEREEKIT_BACKEND", "bedrock")
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    assert isinstance(_backend(), FakeBackend)


def test_bedrock_carries_the_retention_attestation(monkeypatch):
    """An unset attestation must reach the backend as False, not as absent."""
    monkeypatch.setenv("REFEREEKIT_BACKEND", "bedrock")
    monkeypatch.delenv("REFEREEKIT_ZERO_RETENTION", raising=False)
    b = _backend()
    assert isinstance(b, BedrockBackend)
    assert b.zero_retention is False


def test_unknown_transport_is_refused(monkeypatch):
    """A misspelled transport must not silently become a different one.

    Falling through to the default would send the manuscript over a transport
    the referee did not ask for, under an attestation made about a different
    account. Naming a transport that does not exist is a configuration error.
    """
    monkeypatch.setenv("REFEREEKIT_BACKEND", "bedrok")
    monkeypatch.setenv("REFEREEKIT_ZERO_RETENTION", "1")
    with pytest.raises(ValueError, match="bedrok"):
        _backend()
