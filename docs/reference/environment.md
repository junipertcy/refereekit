# Environment variables

This page lists every environment variable that affects refereekit's
behaviour — the ones refereekit reads itself, and the ones the Anthropic SDK
reads on its own — with what each defaults to when it is left unset.

## Variables refereekit reads

| Variable | Read by | Unset means |
|---|---|---|
| `REFEREEKIT_FAKE` | `_backend()` in `cli.py:21` — `1` selects the fake backend | the real SDK backend |
| `REFEREEKIT_FAKE_TEXT` | `cli.py:22` — the string the fake backend returns for every call | `draft` |
| `REFEREEKIT_BACKEND` | `cli.py:27` — deployment name: `anthropic`, `bedrock`, `vertex`; anything else is refused | `anthropic` |
| `REFEREEKIT_MODEL` | `cli.py:31` — model id, else the deployment's confirmed default (`llm.py:53-70`) | `claude-opus-4-8` on `anthropic`, `anthropic.claude-opus-5` on `bedrock`, refusal on `vertex` |
| `REFEREEKIT_ZERO_RETENTION` | `cli.py:34` — `1` attests the backend's account is zero-retention; `complete()` refuses otherwise (`llm.py:32-35`) | the manuscript path refuses to send |
| `REFEREEKIT_STYLE` | `cli.py:162,178,228,359` — style guide path; `--style` overrides | `style/STYLE.md` in the checkout |
| `REFEREEKIT_VENUE_POLICY` | `policy.py:54` — TOML file extending the built-in venue table | built-in table only (one entry, NeurIPS) |
| `OPENREVIEW_USERNAME` / `OPENREVIEW_PASSWORD` | `openreview/client.py:43-47` — `or-fetch` only; an empty value counts as unset | `or-fetch` refuses |

`REFEREEKIT_BACKEND` defaults to `anthropic` only because it is the
deployment a referee with an API key already has, not because it is
preferred over `bedrock` or `vertex` — the next table lists what each of
those two need beyond this one.

Two other entries compete with something else, rather than standing alone.
On `draft`, `editor`, `review` and `or-draft`, `--style` beats
`REFEREEKIT_STYLE`, which beats the checkout's own `style/STYLE.md` — see
[the command reference](cli.md) for which subcommands accept the flag.
`REFEREEKIT_MODEL` beats the per-deployment default in the table above, and
on `vertex` it is not optional: that deployment has no confirmed default, so
`draft`, `editor`, `review` and `or-draft` refuse rather than guess at a
model id.

## Variables the SDK reads

None of these are read by refereekit. `REFEREEKIT_BACKEND` only names a
deployment; the Anthropic SDK reads the rest of that deployment's
configuration directly from the environment, the same variables its
provider's own tooling uses.

| Deployment | Variables |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `bedrock` | `AWS_REGION`, `AWS_PROFILE`, and the rest of the AWS credential chain (`~/.aws/config`, SSO) |
| `vertex` | `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID`, and Google Application Default Credentials (`gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS`) — *documented from the SDK's code, not from a run* |

The `vertex` row is documented from the SDK's own source
(`anthropic/lib/vertex/_client.py` in the installed package), not from a run
against a Vertex project — the same gap as `REFEREEKIT_MODEL` above: no
model id has been confirmed against that deployment either. The SDK also
reads `ANTHROPIC_BEDROCK_BASE_URL`, `AWS_BEARER_TOKEN_BEDROCK`, and
`ANTHROPIC_VERTEX_BASE_URL` for a custom endpoint or bearer-token
authentication; most setups need neither.

## Loading them

refereekit reads all of the variables above from the process environment
only, and never parses `.env` itself: a password in a flag lands in shell
history and the process table, and a password in a file the tool parses is
one path-traversal away from being read by something else. Loading `.env`
into your shell is your job — see [Install](../install.md) for how.

## See also

- [Command reference](cli.md) — every flag that can override one of these
  variables.
- [Confidentiality](../concepts/confidentiality.md) — what
  `REFEREEKIT_ZERO_RETENTION` attests, and what it does not.
