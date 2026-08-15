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


class BedrockBackend:
    """Thin real backend over AWS Bedrock. Not unit-tested against the network.

    Bedrock is a separate transport, not a variant of the first-party API: AWS,
    not Anthropic, is the data processor, so Anthropic's retention terms do not
    govern it. Whether prompts are retained is a property of the account —
    model-invocation logging on or off — which is why `zero_retention` is a
    constructor argument rather than a fixed attribute. A backend that cannot
    express "not checked" cannot fail closed.

    The call streams because a thinking model can exceed the non-streaming
    timeout on a long manuscript prompt, and `max_tokens` defaults well above
    AnthropicBackend's 4096 because thinking and text share that budget.
    """

    def __init__(self, model: str, zero_retention: bool,
                 region: str = "us-east-1", max_tokens: int = 16000):
        import anthropic  # lazy: package imports without the SDK

        self.zero_retention = zero_retention
        self._model = model
        self._max_tokens = max_tokens
        self._client = anthropic.AnthropicBedrockMantle(aws_region=region)

    def __call__(self, prompt: str) -> str:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            msg = stream.get_final_message()
        return "".join(
            b.text for b in msg.content if getattr(b, "type", None) == "text"
        )


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
