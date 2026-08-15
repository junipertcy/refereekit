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


# The Anthropic SDK speaks one messages API to every deployment it supports, so
# which deployment refereekit talks to is a *client*, not a class. Each entry is
# a factory and the model id that deployment uses, because the same model is
# named differently on each and one default cannot serve all of them.
#
# Nothing here is privileged: the direct API is the default only because it is
# the one a referee with an API key already has.
DEPLOYMENTS: dict[str, dict] = {
    "anthropic": {
        "client": lambda: _sdk().Anthropic(),
        "model": "claude-opus-4-8",
    },
    "bedrock": {
        # Region and credentials come from the usual AWS chain, which the SDK
        # reads itself; refereekit never touches them.
        "client": lambda: _sdk().AnthropicBedrockMantle(),
        "model": "anthropic.claude-opus-5",
    },
    "vertex": {
        "client": lambda: _sdk().AnthropicVertex(),
        "model": "claude-opus-4-8@20260115",
    },
}


class DeploymentError(ValueError):
    """Raised when a deployment cannot be constructed.

    A ValueError so the CLI's existing handlers report it as a clean error
    rather than a traceback: the SDK signals missing region or credentials with
    AnthropicError, which is not one.
    """


class UnknownDeployment(DeploymentError):
    """Raised for a deployment name that is not registered.

    Distinct from the plain ValueError the SDK raises for a real deployment that
    is misconfigured, so that "you typed it wrong" cannot be mistaken for "your
    region is unset".
    """


def _sdk():
    import anthropic  # lazy: the package imports without the SDK installed
    return anthropic


def _entry(name: str) -> dict:
    try:
        return DEPLOYMENTS[name]
    except KeyError:
        raise UnknownDeployment(
            f"unknown deployment {name!r}; expected one of "
            f"{', '.join(sorted(DEPLOYMENTS))}"
        ) from None


def default_model(name: str) -> str:
    return _entry(name)["model"]


def client_for(name: str):
    """Build the SDK client for a deployment. Configuration is the SDK's job.

    Region, project and credentials are read by the SDK from the same
    environment the provider's own tooling uses, so refereekit never handles
    them and never has to be taught a new provider's config scheme.
    """
    factory = _entry(name)["client"]
    try:
        return factory()
    except UnknownDeployment:
        raise
    except Exception as e:
        # The SDK's message names the exact variable to set, which is more
        # useful than anything this layer could say; only the type is wrong.
        raise DeploymentError(f"cannot use deployment {name!r}: {e}") from e


class AnthropicBackend:
    """Backend over the Anthropic SDK. Not unit-tested against the network.

    The deployment is injected as a client rather than subclassed, because every
    deployment the SDK offers exposes the same messages API and differs only in
    how the client is constructed. That also makes the backend testable without
    a network.

    The call streams: a thinking model can exceed the non-streaming timeout on a
    long manuscript prompt. max_tokens is high because thinking and text share
    that budget, and the previous 4096 truncated a reasoning model mid-answer.
    """

    def __init__(self, model: str, zero_retention: bool, *, client=None,
                 api_key: str | None = None, max_tokens: int = 16000):
        self.zero_retention = zero_retention
        self.client = client if client is not None else (
            _sdk().Anthropic(api_key=api_key) if api_key
            else client_for("anthropic")
        )
        self._model = model
        self._max_tokens = max_tokens

    def __call__(self, prompt: str) -> str:
        with self.client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            msg = stream.get_final_message()
        return "".join(
            b.text for b in msg.content if getattr(b, "type", None) == "text"
        )
