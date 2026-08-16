# Install

This page installs refereekit in two parts, because the two halves need
different things of you.

Part 1 gets the `refereekit` command working. It needs no key, no account
and no network beyond the install itself, and it is everything [the
tutorial](tutorial.md) uses. Part 2 adds the model access and the
OpenReview credentials a real review needs, and can wait until you need
them.

## Part 1: get it running

```bash
git clone <repository url> refereekit
cd refereekit
python3 --version          # 3.11 or later
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/refereekit --help
```

Python 3.11 or later (`pyproject.toml:4`), because a review spec is TOML
and `tomllib`, the parser it is read with, is in the standard library from
3.11 (`refereekit/spec.py`).

The install takes exactly one runtime dependency, PyMuPDF, which reads the
PDF (`pyproject.toml:8`). Nothing else is needed to ingest, verify, serve
or run a whole review against the offline backend, and the `pip install`
line is the only step in Part 1 that touches the network.

**`-e` is required, not a convenience.** refereekit finds its default
style guide relative to its own source file: `_DEFAULT_STYLE` in
`refereekit/cli.py:17` is the package directory's parent plus
`style/STYLE.md`. But `style/` is a repository asset, not part of the
installed package — `pyproject.toml` installs `refereekit*` and nothing
else. After a plain `pip install .` that parent is `site-packages`, so
`review`, `draft` and `editor` stop, with exit status 2, on
`error: Style guide not found: …/site-packages/style/STYLE.md` — the
message `refereekit/style.py` raises when the path does not exist. An
editable install leaves that parent as your checkout, where
`style/STYLE.md` actually is.

The last command lists the subcommands; its output starts:

```text
usage: refereekit [-h]
                  {ingest,verify,serve,draft,editor,mem-store,mem-recall,review,or-fetch,or-draft,or-responses} ...
```

PyMuPDF 1.28.2, the version a fresh install picked up on 2026-08-15
(`https://pypi.org/project/PyMuPDF/1.28.2/`), adds one more line above
those two: a deprecation warning about the `fitz` alias that
`refereekit/ingest.py` still imports. It is harmless, but it goes to
stdout rather than stderr, so redirect a command's output with that in
mind.

`.venv/bin/refereekit` works from anywhere without activating the virtual
environment. If you would rather type `refereekit`, activate it first —
`source .venv/bin/activate`, or `. .venv/bin/activate.fish` under fish.
Every command in these pages is shown the second way, as `refereekit`,
with the environment active.

You can now run the [tutorial](tutorial.md).

## Part 2: model access and OpenReview

None of this is needed until you review a real paper, and most of it needs
an account somewhere. The optional extras are independent of each other:

| Extra | Installs | Needed for |
|---|---|---|
| `llm` | the Anthropic SDK | `draft`, `editor`, `review`, `or-draft` and `or-responses` against a real model |
| `openreview` | `openreview-py` | `or-fetch` alone — signing in and downloading the submission and its review form |
| `dev` | pytest | running refereekit's own test suite; nothing a review needs |

```bash
.venv/bin/pip install -e ".[llm,openreview]"
```

Name a single extra — `".[llm]"` or `".[openreview]"` — if you only need
the one. Keep the `-e`, for the reason Part 1 gives; dropping it here
breaks the style guide just as thoroughly.

### The three deployments

There is one backend, over the Anthropic SDK, and `REFEREEKIT_BACKEND`
chooses which deployment of that SDK carries the manuscript. A name that
is not one of the three below is refused rather than quietly treated as
the default, because a misspelling must not send a manuscript somewhere
you did not choose.

| Deployment | Install | Variables the SDK reads | Default model |
|---|---|---|---|
| `anthropic` | `pip install -e ".[llm]"` | `ANTHROPIC_API_KEY` | `claude-opus-4-8` |
| `bedrock` | `pip install "anthropic[bedrock]"` | `AWS_REGION`, `AWS_PROFILE`, and the rest of the AWS credential chain | `anthropic.claude-opus-5` |
| `vertex` | `pip install "anthropic[vertex]"` | `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID`, Google Application Default Credentials | none — set `REFEREEKIT_MODEL` |

Not one of the variables in the third column is read by refereekit. Each
deployment's client reads its own configuration from the same environment
that provider's own tooling uses (`refereekit/llm.py`), so refereekit
never handles a credential and never has to learn a new provider's
configuration scheme.

#### anthropic

The direct API, and the default — only because it is the deployment a
referee with an API key already has, not because it is preferred over the
other two (`refereekit/llm.py:39-52`).

*Not run while writing this page: needs an API key.*

```bash
.venv/bin/pip install -e ".[llm]"
export ANTHROPIC_API_KEY=<your key>
export REFEREEKIT_ZERO_RETENTION=1
refereekit draft --session work/tutorial
```

`REFEREEKIT_BACKEND` can stay unset. The model defaults to
`claude-opus-4-8`; `REFEREEKIT_MODEL` overrides it.

#### bedrock

Claude through your own AWS account. The `llm` extra installs the
Anthropic SDK alone, so boto3 and botocore come from the SDK's own extra.
The client refereekit registers here is the SDK's Bedrock Mantle client,
which signs for the `bedrock-mantle` service at
`https://bedrock-mantle.<region>.api.aws/anthropic` — check region
availability and IAM against that.

*Not run while writing this page: needs an AWS account.*

```bash
.venv/bin/pip install "anthropic[bedrock]"
export AWS_REGION=<your region>
export AWS_PROFILE=<your profile>
export REFEREEKIT_BACKEND=bedrock
export REFEREEKIT_ZERO_RETENTION=1
refereekit draft --session work/tutorial
```

`AWS_REGION` and `AWS_PROFILE` are read by the AWS SDK exactly as any
other AWS tool reads them, and `~/.aws/config` works as it always does.
The model defaults to `anthropic.claude-opus-5`. An SSO-based profile
additionally needs the CRT extra:
`.venv/bin/pip install "botocore[crt]"`.

#### vertex

Claude through your own Google Cloud project. Signing in is Google
Application Default Credentials, so `gcloud` holds the credential and
refereekit never sees one.

*Not run while writing this page: needs a Google Cloud project.*

```bash
.venv/bin/pip install "anthropic[vertex]"
gcloud auth application-default login
export CLOUD_ML_REGION=<your region>
export ANTHROPIC_VERTEX_PROJECT_ID=<your project>
export REFEREEKIT_BACKEND=vertex
export REFEREEKIT_MODEL=<the model id your project serves>
export REFEREEKIT_ZERO_RETENTION=1
refereekit draft --session work/tutorial
```

`REFEREEKIT_MODEL` is not optional on this deployment, and the refusal
that says so is real — you can see it offline, with no key and no project,
with `REFEREEKIT_FAKE` unset: the fake backend is marked zero-retention and
never builds an SDK client, so with it still exported from [the
tutorial](tutorial.md) the command below drafts instead of refusing.

```bash
unset REFEREEKIT_FAKE      # bash, zsh
set -e REFEREEKIT_FAKE     # fish
```

```bash
REFEREEKIT_BACKEND=vertex refereekit draft --session work/tutorial
```

```text
error: deployment 'vertex' has no confirmed default model; set REFEREEKIT_MODEL to the id you want to use
```

The exit status is 2. Every command that builds a backend — `draft`,
`editor`, `review`, `or-draft` and `or-responses` — refuses the same way.

#### Why the defaults name different model generations

The table above names `claude-opus-4-8` on `anthropic`,
`anthropic.claude-opus-5` on `bedrock`, and nothing at all on `vertex`.
That is not an oversight. Each deployment names the same models
differently, so one default cannot serve all three, and a default is
recorded only where that id has been run against that deployment.

A fabricated id would be worse than none: it looks authoritative, gets
copied into scripts and documentation, and then fails at the provider with
an error naming the model rather than the mistake. Where no id has been
confirmed, refereekit asks for one instead of guessing
(`refereekit/llm.py:39-52`). `vertex` is in that state today — the client
is real SDK code, the model id has never been confirmed — which is why the
Vertex setup above is marked as unrun and why it sets `REFEREEKIT_MODEL`.

### The attestation

`REFEREEKIT_ZERO_RETENTION=1` appears in all three blocks above because
without it the manuscript path refuses to send anything at all. It is an
attestation you make, not something refereekit can check, and what you are
asserting depends on which deployment you chose.
[Confidentiality](concepts/confidentiality.md#the-attestation) has the
row-by-row table of what `=1` asserts on each, and says who the data
processor is on each; read the row that applies to you before you set it.

### Your .env

```bash
cp .env.template .env
# then edit .env, and load it:
source scripts/load-env.fish        # fish
set -a; . ./.env; set +a            # bash, zsh
```

refereekit reads the process environment only and never parses `.env`
itself: a password in a command-line flag lands in shell history and in
the process table, and a password in a file the tool parses is one
path-traversal away from being read by something else. Loading is the
shell's job, which is why `.env.template` carries both recipes in its own
header. Under PowerShell there is no loader — set the variables by hand.

`scripts/load-env.fish` exists only because fish cannot `source` a
`KEY=value` file the way bash and zsh can, and it must be sourced rather
than executed, since a child process cannot set variables in its parent.
For a `.env` that sets only `REFEREEKIT_FAKE=1` it prints:

```text
load-env: exported 1 variable(s): REFEREEKIT_FAKE
```

Names, never values: a printed password would sit in the scrollback of
every session that loaded it. A key left blank in `.env` is skipped rather
than exported empty, which matters for the next section.

### OpenReview

`or-fetch` signs in with `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD`,
both already listed in `.env.template`. Both are required, and an empty
value is rejected exactly as an absent one is — so a `.env` with the
username filled in and the password left blank fails the same way an
untouched one does, rather than attempting a login. The other two
OpenReview commands, `or-draft` and `or-responses`, work from what
`or-fetch` already downloaded and need neither the credentials nor the
`openreview` extra. [Reviewing on
OpenReview](guides/openreview-review.md) walks through the whole
sequence.

## Next

- [Tutorial](tutorial.md) — a complete review, offline, on Part 1 alone.
- [Reviewing for a journal](guides/journal-review.md) — the first real
  review, once Part 2 is done.
- [Environment variables](reference/environment.md) — every variable named
  on this page, with what leaving it unset means.
