from typing import Protocol, Callable, Union, runtime_checkable


class RetentionError(RuntimeError):
    pass


@runtime_checkable
class Complete(Protocol):
    zero_retention: bool

    def __call__(self, prompt: str) -> str:
        ...


class FakeBackend:
    def __init__(
        self,
        canned: Union[str, Callable[[str], str]],
        zero_retention: bool = True,
    ):
        self._canned = canned
        self.zero_retention = zero_retention

    def __call__(self, prompt: str) -> str:
        return self._canned(prompt) if callable(self._canned) else self._canned


def complete(
    prompt: str, *, backend: Complete, manuscript_ok: bool = False
) -> str:
    if getattr(backend, "zero_retention", False) is not True:
        raise RetentionError(
            "refusing to send: backend is not marked zero_retention"
        )
    return backend(prompt)


class AnthropicBackend:
    """Thin real backend. Not unit-tested against the network."""

    def __init__(
        self, model: str, zero_retention: bool, api_key: str | None = None
    ):
        import anthropic  # lazy: package imports without the SDK

        self.zero_retention = zero_retention
        self._model = model
        self._client = (
            anthropic.Anthropic(api_key=api_key)
            if api_key
            else anthropic.Anthropic()
        )

    def __call__(self, prompt: str) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            b.text for b in msg.content if getattr(b, "type", None) == "text"
        )
