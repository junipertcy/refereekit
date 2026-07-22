import pytest
from refereekit.llm import complete, FakeBackend, RetentionError


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
