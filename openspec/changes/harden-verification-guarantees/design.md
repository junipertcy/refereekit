# Design

## 1. Equation anchors: the contiguous run

**Rule.** Take the extracted numeric equation ids, sort them, and walk from 1
while each is exactly one more than the last. PASS only inside that run.

Measured on the fixtures:

| Fixture | Extracted numeric ids | Run | Rejected |
|---|---|---|---|
| `real_paper.pdf` | 1–7, 18, 19, 20, 22, 30, 39, 44, 50, 55, 82, 311, 490, 500 | 1–7 | 13 |
| `sample_paper.pdf` | none | none | — |

Every genuine label survives; every noise id is rejected. Figures need no
equivalent: they come from caption lines, and the same fixture yields exactly
1–4 with no noise.

**Why anchor at 1 rather than at the lowest extracted id.** Papers number
equations from 1. Anchoring at the minimum would let a low noise id become the
floor and drag a false run up behind it. Anchoring at 1 fails closed when
extraction misses `(1)`: the run is empty and everything FAILs, which is the
safe direction.

**Why FAIL and not FLAG.** FLAG looks like the honest verdict for best-effort
extraction, and it is wrong here. `agent/loop.py` records FLAG anchors into the
claim pool on purpose, so that a bare page pointer stays citable. An equation id
of 500 admitted on those terms is available to the draft with only a soft note —
nearly as harmful as PASS and easier to miss. FAIL keeps it out.

**Residual, stated rather than fixed.** A real equation above the run still
FAILs when extraction missed the ids between. That is pre-existing behaviour for
any unextracted id, and it errs toward refusing. Section-numbered labels
(`2.1`, `3.4`) are not numeric and keep today's behaviour; they remain a known
gap in the same best-effort caveat the README already carries.

## 2. Deployment defaults

Registry entries gain an explicit distinction between *a default that has been
run* and *no default*. `default_model()` raises `DeploymentError` for the latter,
naming `REFEREEKIT_MODEL`; construction is otherwise unchanged.

**`vertex` keeps its client and loses its model.** The client factory is real —
`AnthropicVertex` ships in the SDK. Only the version-suffixed id was invented.
Deleting the deployment would over-correct by discarding working code because of
a fabricated string; leaving the id would keep the defect. Marking it unconfirmed
records the truth and generalises: the next deployment added without a real run
gets the same treatment instead of a plausible guess.

The alternative — remove `vertex` entirely — is defensible on the grounds that
the package should not carry deployments nobody here runs. Rejected because the
mechanism, not the entry, is the point of this requirement.

## 3. Gate coverage by discovery

A test that lists the gated commands is the same artefact that let
`or-responses` slip: the list and the code drift, and nothing notices.

Instead, enumerate the CLI's subparsers, and for each, run it against a session
whose venue prohibits outside models with `_backend()` replaced by a factory that
raises on construction. A command that reaches the backend fails the test. A
command that exits non-zero without constructing one passes. Commands that never
touch a model pass trivially.

This inverts the maintenance burden. Adding a subcommand adds a case
automatically; the only way to make the check stale is to remove the command
surface it reads.

**Known limit.** It proves the *venue* gate holds, not that a command handles the
manuscript correctly in every other respect. Argument shapes differ per command,
so each needs a minimal invocation fixture — the cost of the approach, and still
cheaper than a list.
