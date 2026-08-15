"""Backend selection: which deployment `_backend()` talks to, and what it attests.

The deployment is chosen by environment because it is a property of the machine
and account the referee is sitting at, not of the paper under review.
"""
import anthropic
import pytest

from refereekit.cli import _backend
from refereekit.llm import AnthropicBackend, FakeBackend, UnknownDeployment


def test_the_direct_api_is_the_default(monkeypatch):
    monkeypatch.delenv("REFEREEKIT_BACKEND", raising=False)
    b = _backend()
    assert isinstance(b, AnthropicBackend)
    assert isinstance(b.client, anthropic.Anthropic)


def test_a_deployment_selects_its_client(monkeypatch):
    """Selecting Bedrock changes the client, not the class: there is one backend."""
    monkeypatch.setenv("REFEREEKIT_BACKEND", "bedrock")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    b = _backend()
    assert isinstance(b, AnthropicBackend)
    assert isinstance(b.client, anthropic.AnthropicBedrockMantle)


def test_the_model_default_follows_the_deployment(monkeypatch):
    """Deployments name the same model differently, so the default must track it."""
    monkeypatch.delenv("REFEREEKIT_MODEL", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("REFEREEKIT_BACKEND", "bedrock")
    assert _backend()._model.startswith("anthropic.")
    monkeypatch.setenv("REFEREEKIT_BACKEND", "anthropic")
    assert not _backend()._model.startswith("anthropic.")


def test_fake_wins_over_a_configured_deployment(monkeypatch):
    """Offline mode must not be defeated by a leftover deployment setting."""
    monkeypatch.setenv("REFEREEKIT_BACKEND", "bedrock")
    monkeypatch.setenv("REFEREEKIT_FAKE", "1")
    assert isinstance(_backend(), FakeBackend)


def test_the_retention_attestation_is_carried(monkeypatch):
    """An unset attestation must reach the backend as False, not as absent."""
    monkeypatch.delenv("REFEREEKIT_ZERO_RETENTION", raising=False)
    assert _backend().zero_retention is False
    monkeypatch.setenv("REFEREEKIT_ZERO_RETENTION", "1")
    assert _backend().zero_retention is True


def test_an_unknown_deployment_is_refused(monkeypatch):
    """A misspelled deployment must not silently become a different one.

    Falling through to the default would send the manuscript over a deployment
    the referee did not ask for, under an attestation made about a different
    account.
    """
    monkeypatch.setenv("REFEREEKIT_BACKEND", "bedrok")
    monkeypatch.setenv("REFEREEKIT_ZERO_RETENTION", "1")
    with pytest.raises(UnknownDeployment, match="bedrok"):
        _backend()
