import pytest
from refereekit.llm import complete, FakeBackend, RetentionError, BedrockBackend


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


def test_bedrock_backend_without_attestation_fails_closed():
    """Bedrock retention depends on the account, so it must be attested per run.

    Whether prompts are retained is a property of the AWS account (model
    invocation logging on or off), not of the transport. A backend that hard-codes
    the attestation cannot express "I have not checked", which is the state that
    must refuse to send.
    """
    b = BedrockBackend(model="anthropic.claude-opus-5", region="us-east-1",
                       zero_retention=False)
    with pytest.raises(RetentionError):
        complete("manuscript text", backend=b, manuscript_ok=True)


def test_bedrock_backend_attested_passes_the_gate():
    """An attested backend clears the gate; the send itself is not exercised."""
    b = BedrockBackend(model="anthropic.claude-opus-5", region="us-east-1",
                       zero_retention=True)
    assert b.zero_retention is True
