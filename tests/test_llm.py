import pytest
from refereekit.llm import (complete, FakeBackend, RetentionError,
                           AnthropicBackend, DEPLOYMENTS, UnknownDeployment,
                           DeploymentError, default_model,
                           client_for, default_model)


def test_zero_retention_backend_returns_text():
    b = FakeBackend("hello draft", zero_retention=True)
    assert complete("prompt", backend=b, manuscript_ok=True) == "hello draft"


def test_non_zero_retention_fails_closed():
    b = FakeBackend("should not send", zero_retention=False)
    with pytest.raises(RetentionError):
        complete("prompt", backend=b, manuscript_ok=True)


def test_callable_canned_receives_prompt():
    b = FakeBackend(lambda p: f"echo:{p}", zero_retention=True)
    assert complete("XYZ", backend=b) == "echo:XYZ"


def test_missing_zero_retention_attr_fails_closed():
    """Backend without zero_retention attribute should fail closed."""
    class NoAttrBackend:
        def complete(self, prompt):
            return "should not see this"
    with pytest.raises(RetentionError):
        complete("prompt", backend=NoAttrBackend(), manuscript_ok=True)


def test_backend_accepts_an_injected_client():
    """The SDK speaks the same messages API to every deployment it supports, so
    which deployment is a client, not a class. Injection is also what lets this
    be tested without a network."""
    sentinel = object()
    b = AnthropicBackend(model="m", zero_retention=True, client=sentinel)
    assert b.client is sentinel


def test_backend_without_attestation_fails_closed():
    """Retention is a property of the account behind the client, so it must be
    stated per run. A backend that cannot express "not checked" cannot refuse."""
    b = AnthropicBackend(model="m", zero_retention=False, client=object())
    with pytest.raises(RetentionError):
        complete("manuscript text", backend=b, manuscript_ok=True)


def test_client_for_builds_the_sdk_class_for_a_deployment(monkeypatch):
    """Deployment config is the SDK's job, not refereekit's: Bedrock reads
    AWS_REGION itself, exactly as the AWS tooling around it does."""
    import anthropic
    assert isinstance(client_for("anthropic"), anthropic.Anthropic)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    assert isinstance(client_for("bedrock"), anthropic.AnthropicBedrockMantle)


def test_an_unconfigured_deployment_reports_cleanly(monkeypatch):
    """The SDK raises AnthropicError, which is not a ValueError, so it would
    escape the CLI's handlers and print a traceback. It is re-raised as a
    DeploymentError -- a ValueError -- with the SDK's own guidance kept."""
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    with pytest.raises(DeploymentError, match="AWS_REGION"):
        client_for("bedrock")


def test_an_unknown_deployment_raises_its_own_error():
    """Distinct from ValueError: the SDK raises that for a misconfigured but
    real deployment, and 'you typed it wrong' must not look like 'your region
    is unset'."""
    with pytest.raises(UnknownDeployment, match="bedrok"):
        client_for("bedrok")


# --- deployment defaults carry provenance -----------------------------------

def test_a_confirmed_default_needs_no_model_id():
    """A deployment that has been run against its provider can name its model."""
    assert default_model("anthropic")
    assert default_model("bedrock")


def test_a_deployment_without_a_confirmed_default_refuses():
    """A fabricated default is worse than none: it looks authoritative, gets
    copied into scripts, and fails at the provider with an error naming the
    model rather than the mistake."""
    with pytest.raises(DeploymentError, match="REFEREEKIT_MODEL"):
        default_model("vertex")


def test_every_deployment_states_whether_its_default_is_confirmed():
    """No third state. An entry either vouches for a model id or says it has
    none, so the next deployment added cannot quietly carry a guess."""
    for name, entry in DEPLOYMENTS.items():
        assert "model" in entry, f"{name} does not state a model"
        assert entry["model"] is None or isinstance(entry["model"], str)


def test_no_deployment_ships_a_model_id_that_was_never_run():
    """Pins the specific defect: claude-opus-4-8@20260115 was invented."""
    assert DEPLOYMENTS["vertex"]["model"] is None
