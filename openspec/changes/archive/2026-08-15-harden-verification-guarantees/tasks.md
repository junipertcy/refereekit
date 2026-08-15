# Tasks

Test-first throughout, matching the existing suite: write the failing test,
watch it fail for the right reason, then implement.

## 1. Equation anchors

- [x] 1.1 Add `tests/test_verify_equation_run.py`: an id inside the contiguous
      run PASSes; one above it FAILs; a gap ends the run; a document with no
      extracted ids PASSes nothing
- [x] 1.2 Add a regression case built from `real_paper.pdf` asserting that ids
      1–7 PASS and 500 FAILs, so the fixture's own noise is pinned
- [x] 1.3 Assert the out-of-run verdict is FAIL and never FLAG, naming the claim
      pool in the test's rationale
- [x] 1.4 Implement the contiguous-run computation in `refereekit/verify.py`
- [x] 1.5 Distinguish the two refusals in the evidence string: outside the
      trustworthy range vs. not extracted at all
- [x] 1.6 Confirm no existing test regresses, in particular
      `test_existing_equation_passes`, which picks a low id deliberately

## 2. Deployment defaults

- [x] 2.1 Add tests: a deployment with a confirmed default builds with
      `REFEREEKIT_MODEL` unset; one without refuses and names `REFEREEKIT_MODEL`;
      the same deployment builds when the variable is set
- [x] 2.2 Add a test asserting every registry entry either carries a confirmed
      default or is explicitly marked as having none — no third state
- [x] 2.3 Implement the distinction in `DEPLOYMENTS` and `default_model()` in
      `refereekit/llm.py`, raising `DeploymentError`
- [x] 2.4 Mark `vertex` as having no confirmed default and remove the invented
      `claude-opus-4-8@20260115`
- [x] 2.5 Update the deployment table in `README.md` and the
      `REFEREEKIT_BACKEND` / `REFEREEKIT_MODEL` notes in `.env.template`

## 3. Venue gate by discovery

- [x] 3.1 Add `tests/test_venue_gate_coverage.py` that enumerates the CLI's
      subparsers and builds a minimal invocation for each
- [x] 3.2 Replace `_backend()` with a factory that raises on construction, so
      reaching a model is a test failure rather than a network call
- [x] 3.3 Assert every command either refuses non-zero or never constructs a
      backend, against a session whose venue prohibits outside models
- [x] 3.4 Assert the check fails when a gate is removed — delete one gate
      temporarily and confirm the test catches it, then restore
- [x] 3.5 Confirm read-only commands (`ingest`, `verify`, `serve`, `or-fetch`,
      `mem-recall`) pass without being gated

## 4. Close out

- [x] 4.1 Full suite green; record the count in the commit message
- [x] 4.2 Record the equation-anchor resolution in
      `docs/DOGFOOD-FINDINGS-2-2026-07-22.md`, following the existing
      "Resolved by ..." convention, and mark the `report`/`editor_letter` DRY
      helper closed as won't-do with the measurement that decided it
- [x] 4.3 Note in `README.md` under Extraction limits that equation anchors
      above the contiguous run now FAIL, and why
