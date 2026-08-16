# refereekit User Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the fifteen-page user documentation suite under `docs/`, shrink `README.md` to a landing page, delete `QUICKSTART.md`, and land the three prerequisite commits — with every offline command block executed and its real output pasted.

**Architecture:** Plain Markdown, no generator. Reference pages are written first because they are transcribed from the code and everything else links to them; concept pages next; then install, tutorial, guides, troubleshooting, and finally the two index pages that link to everything. Every task ends in a commit of named paths, a passing link check, and — where the page contains commands — the commands having actually been run.

**Tech Stack:** Markdown; the project's own venv at `.venv/` (Python 3.11+, PyMuPDF, `anthropic` 0.120.2, `openreview-py` 2.4.1, pytest 9 already installed); `refereekit` CLI via `.venv/bin/refereekit`; git.

**Spec:** `docs/superpowers/specs/2026-08-15-refereekit-user-docs-design.md` — read it first. Section numbers below (§4.3, §6.1 …) refer to it.

## Global Constraints

Copied from spec §2. Every task's requirements include these.

1. **Markdown only.** No mkdocs, sphinx or any doc dependency.
2. **No file may be named `index.html`** — `.gitignore` ignores that name at every depth (only `diagrams/index.html` is excepted).
3. **No manuscript-derived text, anywhere.** Worked examples use `tests/fixtures/real_paper.pdf` (the author's own public paper) or invented text. Never any output from an existing `work/` session other than the ones this plan creates from the fixture.
4. **Provider-neutral.** `anthropic`, `bedrock`, `vertex` are documented as peers. Direct API is default "only because it is the one a referee with an API key already has" — say it in those terms.
5. **Stage named paths.** Never `git add -A` or `git add .`. Run `git status` before every commit.
6. **Editable install only.** Every documented install is `pip install -e`; `install.md` says why (`_DEFAULT_STYLE` in `refereekit/cli.py:17` resolves `style/STYLE.md` relative to the package file).
7. **Sessions live under `work/`.** Every documented `--session` argument is `work/<name>`. `work/` is git-ignored (`.gitignore` line 75).
8. **Facts about third parties carry a source URL and an "as of" date.**

## Global tooling

Use these exact commands; they are referred to by name from the tasks.

**RK** — the CLI, always through the venv, never a global install:

```bash
RK=/Users/tzuchi/Documents/Workspace/refereekit/.venv/bin/refereekit
```

**FAKE** — the offline backend, and the fixed tutorial text from spec §4.4. Set both before running any `review`/`draft`/`editor` example:

```bash
export REFEREEKIT_FAKE=1
export REFEREEKIT_FAKE_TEXT='On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".'
```

**TUTSESSION** — builds the tutorial session that several pages paste from. Needs FAKE set. Always delete first, so pasted output comes from a clean run:

```bash
rm -rf work/tutorial && printf 'What does the paper study?\n\nminor revision\nPRX\nminor\n\n\n' | $RK review tests/fixtures/real_paper.pdf --session work/tutorial
```

Expected last line: `review complete: work/tutorial/ours/report.txt, work/tutorial/ours/editor.txt (2 flag(s))`.

**LINKCHECK** — every relative link in `docs/` (excluding `docs/superpowers/` and `docs/internal/`) and in `README.md` must resolve. Run from the repo root:

```bash
python3 -c "
import re,pathlib,sys
files=[p for p in pathlib.Path('docs').rglob('*.md') if 'superpowers' not in p.parts and 'internal' not in p.parts]+[pathlib.Path('README.md')]
bad=[]
for m in files:
    for t in re.findall(r'\]\(([^)#\s]+)',m.read_text()):
        if re.match(r'^[a-z]+:',t): continue
        if not (m.parent/t).exists(): bad.append(f'{m}: {t}')
print('\n'.join(bad) or 'links ok'); sys.exit(1 if bad else 0)"
```

**PATHCHECK** — no documented session path outside `work/` (spec §6.7). Must print nothing:

```bash
grep -rnE -- "--session +[A-Za-z0-9./~_-]+" docs/*.md docs/guides docs/reference docs/concepts README.md | grep -vE -- "--session +(\./)?work/" | grep -vE -- "--session +S\b" || true
```

(A bare `` `--session` `` in a table, or `--session <dir>` in a usage line, does not match; a real path that is not under `work/` does.)

**STUBCHECK** — no scaffold stub left (Task 1 writes the marker). Must print nothing:

```bash
grep -rln "This page is being written" docs README.md | grep -v superpowers || true
```

**TESTS** — `.venv/bin/pytest -q` — baseline is **354 passed** (recorded 2026-08-15, ~75 s).

**Scratch sessions:** create them under `work/` in the repo checkout (git-ignored). Delete and recreate a session before re-running a documented block, so pasted output is from a clean run: `rm -rf work/tutorial`.

**`serve` in the background** blocks and, when stdout is a pipe, Python buffers its one line. Verify with:

```bash
PYTHONUNBUFFERED=1 $RK serve --session work/tutorial --port 8888 & sleep 1; curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8888/; kill %1
```

Expected first line: `serving work/tutorial at http://127.0.0.1:8888/` and then `HTTP 200`.

## Writing rules

The reader is a referee with no context (spec §1.1). The author has questionable taste by assumption, so:

- **Voice:** match the existing prose in `README.md` and the spec — declarative sentences with the reason attached ("…, because …"), second person for the reader, no marketing, no exclamation marks, no emoji. British spelling as the codebase uses (`behaviour`, `recognise`, `honours`). Sentence-case headings. Wrap prose at about 80 columns.
- **Every page** starts with an H1 and one plain sentence saying what the page is for; ends with a short **Next** or **See also** line of relative links, because the suite routes readers rather than explaining everything on one page.
- **Commands** go in fenced ```` ```bash ```` blocks, one command per block unless a sequence is the point. **Outputs** go in fenced ```` ```text ```` blocks and are pasted verbatim from a real run (spec §6.1). Show the command as the reader types it (`refereekit …`, not `$RK …`, not `.venv/bin/refereekit …`; `install.md` explains that the venv is on the path once activated or that `.venv/bin/refereekit` works without activating).
- **Unverified blocks** — anything needing a network, an account or a real key (`or-fetch`, `or-draft`, `or-responses`, every real-LLM run, the Bedrock and Vertex setups) — carry, immediately above the block, one italic line: *Not run while writing this page: needs an OpenReview account.* / *…needs an API key.* / *…needs an AWS account.* / *…needs a Google Cloud project.* Never present such a block as tested.
- **Facts about outside parties** (venue policies) carry the URL and "as of 2026-08-15" inline.
- **Links** are relative (`../reference/cli.md`, `install.md#part-1-get-it-running`). Never absolute GitHub URLs. Never link into `docs/superpowers/` from a user page.
- **Do not paste refereekit source** into user pages. Name a file when explaining a "why" (`refereekit/policy.py`), no more.
- **Session paths** are always `work/<name>`.
- Say `refereekit` (lowercase) for the tool, `` `review` `` for a subcommand, `` `--session` `` for a flag.

## Page skeleton and stub marker

Task 1 creates each page as an H1 plus the stub line
`_This page is being written; see docs/superpowers/plans/2026-08-15-refereekit-user-docs.md._`
so every link resolves from the first commit. Each later task **overwrites the whole file** (Write, not Edit) with the finished page. Task 17 checks no stub survives.

The H1s, fixed so links and prose can name them:

| File | H1 |
|---|---|
| `docs/README.md` | `# refereekit documentation` |
| `docs/before-you-start.md` | `# Before you start` |
| `docs/install.md` | `# Install` (with `## Part 1: get it running` and `## Part 2: model access and OpenReview`) |
| `docs/tutorial.md` | `# Tutorial: a complete review, offline` |
| `docs/guides/journal-review.md` | `# Reviewing for a journal` |
| `docs/guides/openreview-review.md` | `# Reviewing on OpenReview` |
| `docs/guides/review-spec.md` | `# Driving a review from a spec` |
| `docs/guides/your-voice.md` | `# Your voice: the style guide and venue memory` |
| `docs/guides/piecemeal.md` | `# The tools on their own` |
| `docs/reference/cli.md` | `# Command reference` |
| `docs/reference/environment.md` | `# Environment variables` |
| `docs/reference/session.md` | `# The session directory` |
| `docs/concepts/verification.md` | `# What verification means` |
| `docs/concepts/confidentiality.md` | `# Confidentiality` |
| `docs/troubleshooting.md` | `# Troubleshooting` |

---

### Task 0: Land the prerequisites (spec §0)

Three commits that must exist before any documentation commit, so the docs branch is docs-only and the test baseline is honest.

**Files:**
- Commit as-is (already modified in the working tree): `refereekit/openreview/client.py`, `tests/openreview_fakes.py`, `tests/test_or_client.py`
- Modify then commit: `AGENTS.md` (untracked; two corrections)
- Commit as-is: `scripts/load-env.fish` (untracked)

- [ ] **Step 1: Confirm the branch and the baseline**

Run: `git branch --show-current` — Expected: `docs/user-docs`.
Run: `git status --short` — Expected exactly: ` M docs/superpowers/specs/2026-08-15-refereekit-user-docs-design.md` (the revised spec), `?? docs/superpowers/plans/2026-08-15-refereekit-user-docs.md` (this plan), ` M refereekit/openreview/client.py`, ` M tests/openreview_fakes.py`, ` M tests/test_or_client.py`, `?? AGENTS.md`, `?? scripts/`, plus `?? aaai-worth-reading/` (unrelated; leave it alone, never stage it).
Run: TESTS — Expected: `354 passed`.

- [ ] **Step 2: Commit the revised spec and this plan**

```bash
git add docs/superpowers/specs/2026-08-15-refereekit-user-docs-design.md docs/superpowers/plans/2026-08-15-refereekit-user-docs.md
git commit -m "docs: revise the user-docs spec after review; add the implementation plan

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 3: Commit the `profile_id` fix on its own**

```bash
git add refereekit/openreview/client.py tests/openreview_fakes.py tests/test_or_client.py
git commit -m "fix: read our profile id from the login response

openreview-py v2 sends an empty query for a bare get_profile() and the API
answers 400, which took out every command that lists assignments. The id
login already stored on the client costs no request.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Correct `AGENTS.md`'s two stale lines**

In `AGENTS.md`, replace this line:

```
- The only committable PDF is the test fixture in `tests/fixtures/`.
```

with:

```
- The only committable PDFs are the two test fixtures in `tests/fixtures/`.
```

and replace this paragraph:

```
**Known gap — read before staging anything:** the manuscript patterns in
`.gitignore` are root-anchored (`/*.pdf`, `/*_raw.txt`, …), so a manuscript PDF
in a *subdirectory* is **not** ignored. Never `git add -A` or `git add .` in
this repo. Stage named paths, and run `git status` before every commit.
```

with:

```
**Read before staging anything:** `.gitignore` denies manuscript files at
every depth and allows this repository's own by name (`tests/test_gitignore.py`
pins both halves), but it protects only `*.pdf`, `index.html` and `work/`; a
session's `doc.json`, `state.json`, `ours/` and `theirs/` anywhere else are
committable. Keep sessions under `work/`. Never `git add -A` or `git add .` in
this repo. Stage named paths, and run `git status` before every commit.
```

Verify: `grep -n "root-anchored\|only committable PDF is" AGENTS.md` prints nothing.

- [ ] **Step 5: Commit `AGENTS.md` and the env loader**

```bash
git add AGENTS.md scripts/load-env.fish
git commit -m "chore: commit the working rules and the fish env loader

Both were referenced by .env.template and the docs spec but never tracked.
AGENTS.md's gitignore paragraph is brought up to date with 7fd6a9e.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Confirm the tree is clean apart from the unrelated folder**

Run: `git status --short` — Expected: only `?? aaai-worth-reading/`.

---

### Task 1: Scaffold the docs tree, move the dogfood reports

**Files:**
- Create: the fifteen files in the H1 table above, each containing its H1, a blank line, and the stub line.
- Move: `docs/DOGFOOD-FINDINGS-2026-07-22.md` and `docs/DOGFOOD-FINDINGS-2-2026-07-22.md` → `docs/internal/`

- [ ] **Step 1: Create the directories and stubs**

```bash
mkdir -p docs/guides docs/reference docs/concepts docs/internal
```

Then Write each of the fifteen files with exactly this shape (H1 from the table; this example is `docs/tutorial.md`):

```markdown
# Tutorial: a complete review, offline

_This page is being written; see docs/superpowers/plans/2026-08-15-refereekit-user-docs.md._
```

- [ ] **Step 2: Move the dogfood reports**

```bash
git mv docs/DOGFOOD-FINDINGS-2026-07-22.md docs/internal/DOGFOOD-FINDINGS-2026-07-22.md
git mv docs/DOGFOOD-FINDINGS-2-2026-07-22.md docs/internal/DOGFOOD-FINDINGS-2-2026-07-22.md
```

- [ ] **Step 3: Verify**

Run: `ls docs docs/guides docs/reference docs/concepts docs/internal` — Expected: the fifteen pages plus `review-spec.example.toml`, `superpowers/`, and the two moved reports.
Run: LINKCHECK — Expected: `links ok` (stubs contain no links; `README.md`'s existing link to `QUICKSTART.md` still resolves).
Run: `git check-ignore -v docs/reference/cli.md docs/README.md` — Expected: no output (nothing ignored).

- [ ] **Step 4: Commit**

```bash
git add docs/README.md docs/before-you-start.md docs/install.md docs/tutorial.md docs/troubleshooting.md docs/guides docs/reference docs/concepts docs/internal
git commit -m "docs: scaffold the user documentation tree

Fifteen stub pages so links resolve from the first commit; the dogfood
post-mortems move to docs/internal/ (spec §5).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `docs/reference/cli.md`

Transcribed from the parser in `refereekit/cli.py:75-116` and the handlers below it. `--help` carries almost no help strings, so the parser is the source; check every flag, `required=True` and default against the lines cited.

**Files:**
- Overwrite: `docs/reference/cli.md`

**Facts to state (source lines in `refereekit/cli.py`):**

| Command | Flags (required in bold) | Defaults | Source |
|---|---|---|---|
| `ingest <pdf>` | **`--session`** | — | 80 |
| `verify` | **`--session`**, **`--kind`**, **`--anchor`**, **`--text`** | — | 81-83 |
| `serve` | **`--session`**, `--port` | `--port 8888` | 84 |
| `draft` | **`--session`**, `--length name=value` (repeatable), `--style` | style: `--style` > `REFEREEKIT_STYLE` > `style/STYLE.md` in the checkout | 85-87, 162 |
| `editor` | **`--session`**, `--answers key=value` (repeatable), `--style` | as `draft` | 88-90, 178 |
| `mem-store` | **`--session`**, **`--venue`**, **`--kind`**, **`--text`**, `--db` | `--db <session>/memory.db` | 91-93, 187 |
| `mem-recall` | **`--venue`**, **`--db`**, `--limit` | `--limit 20` | 94-96 |
| `review <pdf>` | **`--session`**, `--venue`, `--spec`, `--db`, `--style` | `--db <session>/memory.db`; venue = `--venue`, else the spec's, else the session's (219) | 97-104 |
| `or-fetch` | **`--venue`**, **`--session`**, `--number`, `--baseurl` | `--baseurl https://api2.openreview.net` (`refereekit/openreview/client.py:17`) | 105-109 |
| `or-draft` | **`--session`**, `--length name=value` (repeatable), `--style`, `--db` | `--db <session>/memory.db` | 110-114, 381 |
| `or-responses` | **`--session`** | — | 115-116 |

Behaviour per command:

- **`ingest`** creates the session directory (`Session.create`, 122), writes `doc.json`, prints `ingested: 9 pages, 20 equations` for the fixture. Exit 2 with `error: no such file: '<path>'` for a missing PDF (126-128).
- **`verify`** needs an existing session with `doc.json`. `--kind` is `quote` or `page` (both check page text), `equation`, `figure`; any other kind is `FLAG: '<kind>' claim needs human confirmation`, exit 3 (`refereekit/verify.py:103`). Prints `<STATUS>: <evidence>`. Exit 0 PASS, 1 FAIL, 3 FLAG (135-140); 2 for a missing session (`error: [Errno 2] No such file or directory: '…/doc.json'`).
- **`serve`** prints `serving <dir> at http://127.0.0.1:<port>/`, serves the session directory on 127.0.0.1 and runs until interrupted. Never returns 2: a missing session or a session with no `index.html` serves 404s (145-150). If `--port` is busy it takes the next free port, trying 50 (`refereekit/render.py:34-41`), and the printed line shows the port chosen. `index.html` is written by `review` only.
- **`draft`** / **`editor`** need `doc.json`; `state.json` is optional (an empty pool is drafted from and flagged, spec §4.9). The venue gate reads the session's recorded venue (159, 175). Writes `ours/report.txt` / `ours/editor.txt`; prints `report: wrote 124 chars, 1 flag(s)` then one `  FLAG page (3): not in verified pool` line per flag (50-55). A `--length`/`--answers` value without `=` exits 2 with the raw message `error: dictionary update sequence element #0 has length 1; 2 is required` — say that it means "missing `=`". Exit 2 also on `RetentionError`, `VenuePolicyError`, missing style file (166-168, 181-183).
- **`mem-store`** needs `doc.json` (the guard checks the note against it). Prints `stored note for <venue>`. Failures print `mem-store failed: <reason>` (191-192). **`mem-recall`** prints `[<venue>/<kind>] <text>` per note, newest first, deduplicated (`refereekit/memory.py:37-44`); a `--db` path that does not exist is created empty and prints nothing, exit 0 — say so, a typo is silent. Failures `mem-recall failed: …`.
- **`review`** creates the session; parses `--spec` first (210); venue gate before the PDF is opened and before a backend exists (221); opens `memory.db` only when a venue is known (223-225); prints `SUMMARY:` + summary, the Q&A, the gate prompts, and finally `review complete: <report>, <editor> (N flag(s))` — a count only; run `draft` on the session to see the flag lines. Failures print `review failed: <reason>` exit 2 (232-234): missing PDF, spec errors, unknown deployment, retention refusal, venue refusal, a note that repeats the manuscript, EOF on stdin.
- **`or-fetch`** without `--number` lists assignments (`  <number>  <title>` per line, `no assignments for you at <venue>`, `could not read N assigned submission(s): …`, `Fetch one with: --number <N>`; 243-257) exit 0. With `--number`: refuses a session recording a different number (266-270); writes `paper.pdf`, `doc.json`; prints `fetched submission N: P pages`; records `venue`, `number`, `forum`; then best-effort: `review form: X prose field(s), Y to fill in yourself` or `no review form at <venue>/Submission<N>/-/Official_Review (<reason>); skipping form.json`; then `theirs/: A new, B unchanged[, C held back]`, `no replies yet; theirs/ left empty`, or `could not read the discussion for <forum> (<reason>); theirs/ left empty`, and for held-back notes the three lines at 326-330. Exit 2 with `error: …` (332-341).
- **`or-draft`** checks in this order, all before a backend is built (352-375): venue gate; `error: no form.json; run or-fetch --number first`; `error: --length takes name=value, e.g. --length summary=short`; `error: --length names no field in this form: <names>`; `error: no verified claims in this session; run refereekit review <session>/paper.pdf --session <session> first`. Writes `ours/openreview.md`, `ours/openreview.json`; prints `openreview: N prose field(s) drafted, K flag(s)`, FLAG lines, `to fill in yourself:` and one `  <name>  (<span>)  <description>` per blank (389-395).
- **`or-responses`**: venue gate; `error: no session at <dir>; run or-fetch --number first`; `error: no received notes in theirs/; nothing to analyze`; uses `ours/openreview.md`, else `ours/report.txt`, as "our review"; writes `ours/response-analysis.txt`; prints `wrote <path> (N received note(s))` (402-442).

Exit-code section (spec §4.10): `verify` 0/1/3; every other command 0, or 2 on an input error with the reason on stderr; `serve` the exception; argparse's own errors (missing required flag) also exit 2 with a usage line. Error prefixes as printed: `error:` (most), `review failed:`, `mem-store failed:`, `mem-recall failed:`.

- [ ] **Step 1: Run the offline blocks whose output the page pastes**

With FAKE set and from the repo root:

```bash
rm -rf work/ref && $RK ingest tests/fixtures/real_paper.pdf --session work/ref
$RK verify --session work/ref --kind quote --anchor 1 --text "a finite set of nodes"; echo "exit $?"
$RK verify --session work/ref --kind equation --anchor 18 --text ""; echo "exit $?"
$RK verify --session work/ref --kind table --anchor 1 --text "whatever it says"; echo "exit $?"
$RK ingest work/nonexistent.pdf --session work/ref2; echo "exit $?"
```

Expected, in order: `ingested: 9 pages, 20 equations`; `PASS: found on page 1` / `exit 0`; `FAIL: equation (18) is outside the range extraction can vouch for (1-7)` / `exit 1`; `FLAG: 'table' claim needs human confirmation` / `exit 3`; `error: no such file: 'work/nonexistent.pdf'` / `exit 2`.

- [ ] **Step 2: Write the page**

Overwrite `docs/reference/cli.md`: H1; one sentence (this is the reference; the guides say when to use what); a **Conventions** section (`--session` is a directory under `work/`; `ingest`, `review`, `or-fetch` create it, the rest require it; errors go to stderr); one `##` section per command in the order of the table, each with a `bash` usage line, a flags table (flag / required / default / meaning), **Writes**, **Prints** (with the pasted outputs from Step 1 where they exist), **Exit**; then `## Exit codes`; then **See also** → `../guides/piecemeal.md`, `environment.md`, `session.md`, `../troubleshooting.md`.

- [ ] **Step 3: Check the page against the parser**

Open `refereekit/cli.py:75-116` beside the page and tick every `add_argument` — name, `required=True`, `default`, `type`, `action="append"` — against the tables. Then LINKCHECK → `links ok`; PATHCHECK → nothing.

- [ ] **Step 4: Commit**

```bash
git add docs/reference/cli.md
git commit -m "docs: command reference, checked against the parser

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `docs/reference/environment.md` and the `.env.template` additions

**Files:**
- Overwrite: `docs/reference/environment.md`
- Modify: `.env.template` (Bedrock block, and a new Vertex block)

**Facts to state:**

refereekit's own variables (source: `refereekit/cli.py`, `refereekit/policy.py:54`, `refereekit/openreview/client.py:43-47`):

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

Read by the SDK, never by refereekit (spec §4.11; the SDK's own reads at `.venv/lib/python3*/site-packages/anthropic/lib/bedrock/_client.py:77` and `.../vertex/_client.py:46,114`):

| Deployment | Variables |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `bedrock` | `AWS_REGION`, `AWS_PROFILE`, and the rest of the AWS credential chain (`~/.aws/config`, SSO) |
| `vertex` | `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID`, and Google Application Default Credentials (`gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS`) — *documented from the SDK's code, not from a run* |

State that refereekit reads only the environment and never parses `.env` (`.env.template:8-11`), and link to `../install.md` for loading it.

- [ ] **Step 1: Verify the lists against three sources (spec §6.3)**

```bash
grep -n "environ" refereekit/*.py refereekit/openreview/*.py | grep -v '"""' | grep -v "#"
grep -n "^[A-Z_]*=" .env.template
grep -n 'environ.get("' .venv/lib/python3*/site-packages/anthropic/lib/bedrock/_client.py .venv/lib/python3*/site-packages/anthropic/lib/vertex/_client.py
```

Expected: the nine refereekit variables in the first; the twelve template names in the second (`OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD`, `REFEREEKIT_ZERO_RETENTION`, `REFEREEKIT_VENUE_POLICY`, `REFEREEKIT_BACKEND`, `REFEREEKIT_MODEL`, `ANTHROPIC_API_KEY`, `AWS_REGION`, `AWS_PROFILE`, `REFEREEKIT_FAKE`, `REFEREEKIT_FAKE_TEXT`, `REFEREEKIT_STYLE`); `AWS_REGION`, `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID` (plus base-URL and bearer-token variables you may mention in a footnote or omit) in the third.

- [ ] **Step 2: Add the two blocks to `.env.template`**

Replace the Bedrock block:

```
# --- Bedrock deployment only ---
# Read by the AWS SDK, not by refereekit, exactly as any other AWS tool reads
# them. An SSO-based profile also needs the CRT extra:
#     pip install "botocore[crt]"
AWS_REGION=
AWS_PROFILE=
```

with:

```
# --- Bedrock deployment only ---
# The llm extra installs the Anthropic SDK alone; boto3/botocore are the SDK's
# own extra:
#     pip install "anthropic[bedrock]"
# Read by the AWS SDK, not by refereekit, exactly as any other AWS tool reads
# them. An SSO-based profile also needs the CRT extra:
#     pip install "botocore[crt]"
AWS_REGION=
AWS_PROFILE=

# --- Vertex deployment only ---
#     pip install "anthropic[vertex]"
# Read by the SDK, not by refereekit; credentials come from Google Application
# Default Credentials (gcloud auth application-default login). Named here so
# this file and docs/reference/environment.md list the same variables. Not
# yet exercised: no model id has been run against Vertex, so REFEREEKIT_MODEL
# is required on this deployment.
CLOUD_ML_REGION=
ANTHROPIC_VERTEX_PROJECT_ID=
```

- [ ] **Step 3: Write the page**

Overwrite `docs/reference/environment.md`: H1; one sentence; `## Variables refereekit reads` (the first table, one row per variable, plus a sentence each on precedence where it exists: `--style` beats `REFEREEKIT_STYLE`; `REFEREEKIT_MODEL` beats the default); `## Variables the SDK reads` (second table, Vertex row marked as unverified); `## Loading them` (one paragraph: refereekit never parses `.env`; link to `../install.md`); **See also** → `cli.md`, `../concepts/confidentiality.md`.

- [ ] **Step 4: Verify**

Run: TESTS → `354 passed` (the template is not pinned by any test, but confirm). LINKCHECK → `links ok`.

- [ ] **Step 5: Commit**

```bash
git add docs/reference/environment.md .env.template
git commit -m "docs: environment reference; name the Vertex variables in the template

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: `docs/reference/session.md`

**Files:**
- Overwrite: `docs/reference/session.md`

**Facts to state (spec §4.12; sources `refereekit/session.py`, `cli.py`, `render.py`, `agent/loop.py`):**

The tree exactly as in spec §4.12, with the writer of each entry. Creation is lazy: `ours/` on the first draft (`session.py:50-55`), `theirs/` on the first received reply (`session.py:57-63`, only `or-fetch` writes there), `memory.db` only when a venue is known and no `--db` is given (`cli.py:222-225, 187, 381`), `index.html` by `review` only (`render.py:23-25`), `paper.pdf` and `form.json` by `or-fetch` only (`cli.py:281, 301`), `doc.json` by `ingest`, `review`, `or-fetch`.

`state.json` keys and writers: `venue`, `number`, `forum` (`cli.py:286-288`), `invitation_id` (`cli.py:302`) — all `or-fetch`; `verdict` — the verdict gate (`agent/loop.py:50-55`; its `venue` sub-key is what `draft`/`editor` fall back to, `cli.py:39-47`); `claims` — the Q&A loop (`agent/loop.py:106-118`, PASS and FLAG both recorded, FAIL never); `qa_count` — the page renderer (`render.py:25,32`).

Why `ours/`/`theirs/` are separate (spec §4.12 wording). `theirs/` is write-once (`session.py:69-77`, `ProvenanceError`); received notes are named `<note-id>-<tcdate>.txt` (`openreview/client.py:271-310`).

Which entries are manuscript-derived and therefore protected only by living under `work/`: `paper.pdf` and `index.html` are ignored by name anywhere; `doc.json`, `state.json`, `ours/`, `theirs/`, `memory.db` are not (`.gitignore:11-24, 75`).

- [ ] **Step 1: Produce a real listing to paste**

With FAKE set: `rm -rf work/tutorial && printf 'What does the paper study?\n\nminor revision\nPRX\nminor\n\n\n' | $RK review tests/fixtures/real_paper.pdf --session work/tutorial >/dev/null && ls -R work/tutorial && python3 -m json.tool work/tutorial/state.json`

Expected listing: `doc.json index.html ours state.json` and `ours: editor.txt report.txt`; the JSON shows `qa_count: 1`, two claims (`"a finite set of nodes"` on `"1"`, `""` on `"2"`), and the verdict.

- [ ] **Step 2: Write the page**

Overwrite `docs/reference/session.md`: H1; one sentence; `## Layout` (the tree with writers); `## What appears when` (the real listing after the tutorial run, and a sentence on what `or-fetch` adds); `## state.json` (a key/writer table and the pasted JSON); `## ours/ and theirs/`; `## What is manuscript-derived` (the `.gitignore` point, link to `../concepts/confidentiality.md`); **See also** → `cli.md`, `../tutorial.md`.

- [ ] **Step 3: Verify**

Check each writer claim against the cited line. LINKCHECK → `links ok`; PATHCHECK → nothing.

- [ ] **Step 4: Commit**

```bash
git add docs/reference/session.md
git commit -m "docs: session directory reference

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: `docs/concepts/verification.md`

**Files:**
- Overwrite: `docs/concepts/verification.md`

**Facts to state (spec §4.13), each as its own short section in this order:**

1. **Quotation-scoped.** PASS on `page`/`quote` = these exact words, normalized for whitespace and case, are on that page (`refereekit/verify.py:66-73`). Only quoted spans are candidates (`refereekit/quotes.py:1-7`).
2. **A bare citation is FLAG, not PASS** — the common case, because referee prose paraphrases (`verify.py:68-71`).
3. **FLAG carries a guarantee**: the page is checked first, so a citation to a page not in the document is FAIL however little it quotes (`verify.py:53-65`); that is why a FLAG may enter the claim pool (`agent/loop.py:108-116`).
4. **Floors**: quoted spans under 12 characters are skipped as scare-quoting (`quotes.py:12`); fewer than four words verifies as FLAG (`types.py:53`, `verify.py:68`).
5. **Folding, not fuzzy matching**: NFKC, dashes, curly quotes, soft hyphens, words broken across a line — both readings searched (`textnorm.py`); a hyphen inside a line stays content, `58%` does not match `5-8%` (`textnorm.py:70-72`). On FAIL the nearest line is reported as a diagnostic only (`verify.py:10-29`).
6. **Extraction limits**: figures from caption lines (fixture: figures 1–4); an equation anchor passes only inside the contiguous run of extracted ids beginning at 1 — the fixture extracts twenty numeric ids of which 1–7 are the run, so `(18)` FAILs with `outside the range extraction can vouch for (1-7)` (`verify.py:32-49, 88-97`); FAIL rather than FLAG on purpose, because a FLAG would enter the pool; residual: a section-numbered label such as `(2.1)` is outside the run rule and passes on bare existence (`verify.py:81-87`); section detection is best-effort and yields nothing on many papers (the fixture: 0 sections); equation bodies are never reconstructed.
7. **The two draft flags**: `not in verified pool` (the draft cited an anchor the Q&A never established) and `failed re-verification` (it was in the pool but no longer verifies against `doc.json` — a re-fetched, revised paper, or the model altered the quotation) (`drafts.py:98-112`).
8. **What it cannot do**: whether a mathematical claim is true. Human work.

- [ ] **Step 1: Run the reproducible examples**

Build TUTSESSION (Global tooling), then:

```bash
$RK verify --session work/tutorial --kind quote --anchor 1 --text "a finite set of nodes"; echo "exit $?"
$RK verify --session work/tutorial --kind quote --anchor 3 --text "words that are not on that page"; echo "exit $?"
$RK verify --session work/tutorial --kind page --anchor 2 --text "model"; echo "exit $?"
$RK verify --session work/tutorial --kind quote --anchor 99 --text "a finite set of nodes"; echo "exit $?"
$RK verify --session work/tutorial --kind equation --anchor 3 --text ""; echo "exit $?"
$RK verify --session work/tutorial --kind equation --anchor 18 --text ""; echo "exit $?"
$RK verify --session work/tutorial --kind figure --anchor 1 --text ""; echo "exit $?"
```

Expected: `PASS: found on page 1`/0; `FAIL: not found on page 3`/1; `FLAG: page 2 exists; no quotation to verify: 1 words, need 4`/3; `FAIL: page 99 does not exist`/1; `PASS: equation (3) exists`/0; `FAIL: equation (18) is outside the range extraction can vouch for (1-7)`/1; `PASS: figure (1) exists`/0.

- [ ] **Step 2: Write the page**

Overwrite `docs/concepts/verification.md`: H1; one sentence ("what a PASS promises, which is narrower than you will assume"); the eight sections above with the pasted examples placed under sections 1, 3, 4 and 6; **See also** → `confidentiality.md`, `../reference/cli.md`, `../guides/piecemeal.md`.

- [ ] **Step 3: Verify**

Each cited line says what the page says. LINKCHECK → `links ok`; PATHCHECK → nothing.

- [ ] **Step 4: Commit**

```bash
git add docs/concepts/verification.md
git commit -m "docs: what verification means

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: `docs/concepts/confidentiality.md`

**Files:**
- Overwrite: `docs/concepts/confidentiality.md`

**Facts to state (spec §4.14), as sections in this order:**

1. **The one gate**: `complete()` refuses any backend not marked `zero_retention` (`refereekit/llm.py:29-36`); manuscript text reaches a model only through it — and so do author responses (`openreview/responses.py:29-35`).
2. **The attestation**: `REFEREEKIT_ZERO_RETENTION=1` is yours to make; the code checks the flag, not the account (`cli.py:34`). The per-deployment table verbatim from spec §4.14 (anthropic: your organization has a zero-data-retention arrangement; bedrock: your AWS account has no model-invocation logging; vertex: your project's logging and retention settings permit it). On the cloud deployments the provider, not Anthropic, is the data processor.
3. **The venue gate** refuses before a backend is built and before the PDF is opened (`cli.py:221`, `352`, `410`), reading the venue from `--venue`, the spec, or the session state `or-fetch` recorded; the built-in table has one entry and unlisted venues are permitted (`policy.py:10-14, 32-34`); link to `../before-you-start.md`.
4. **The leak guard fails closed**: an empty or unreadable document is a rejection (`guard.py:52-54`); memory stores referee-authored notes only, and a note that repeats the manuscript is refused with `mem-store failed: input is a verbatim manuscript fragment …` (`guard.py:58-62`).
5. **Repository rules**: `work/` is git-ignored and sessions live under it, because `doc.json`, `state.json`, `ours/`, `theirs/`, `memory.db` are manuscript-derived and nothing else in `.gitignore` protects them (`.gitignore:11-24, 75`); the only committable PDFs are the two test fixtures; `style/STYLE.md` is committable, raw reports never; never `git add -A`; `.env` is read by the shell and never parsed by refereekit.
6. **The one outbound request that is not the model**: `index.html` loads MathJax from `cdn.jsdelivr.net` when opened in a browser (`render.py:10`); no page content is sent.

- [ ] **Step 1: Reproduce the two refusals to paste**

Build TUTSESSION (with FAKE set), then with FAKE **unset** (`unset REFEREEKIT_FAKE`) and no key in the environment:

```bash
env -u ANTHROPIC_API_KEY $RK draft --session work/tutorial; echo "exit $?"
REFEREEKIT_FAKE=1 $RK review tests/fixtures/real_paper.pdf --session work/neurips --venue NeurIPS.cc/2026/Conference </dev/null; echo "exit $?"
```

Expected: `error: refusing to send: backend is not marked zero_retention` / `exit 2`; and `review failed: NeurIPS.cc/2026/Conference prohibits sending the submission to an outside model, so this command will not send it. Use the venue's own review interface. If this rule has changed, override it with a REFEREEKIT_VENUE_POLICY file containing:  [venues]` + `    "NeurIPS.cc/2026/Conference" = { llm = true }` / `exit 2`. Then `rm -rf work/neurips`.

- [ ] **Step 2: Write the page**

Overwrite `docs/concepts/confidentiality.md` with the six sections, the two pasted refusals under sections 1 and 3, and **See also** → `verification.md`, `../before-you-start.md`, `../reference/environment.md`.

- [ ] **Step 3: Verify**

Cited lines match. LINKCHECK → `links ok`; PATHCHECK → nothing.

- [ ] **Step 4: Commit**

```bash
git add docs/concepts/confidentiality.md
git commit -m "docs: the confidentiality model end to end

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: `docs/install.md`

**Files:**
- Overwrite: `docs/install.md`

**Content (spec §4.3), with these exact headings and commands:**

`## Part 1: get it running` — the tutorial needs only this.

```bash
git clone <repository url> refereekit
cd refereekit
python3 --version          # 3.11 or later
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/refereekit --help
```

State: Python 3.11+ because `tomllib` (the review spec's parser) is standard library from 3.11 (`pyproject.toml:4`); the only runtime dependency is PyMuPDF; **`-e` is required, not a convenience** — refereekit finds its default style guide relative to its own source (`refereekit/cli.py:17`), so a plain `pip install .` produces `Style guide not found: …/site-packages/style/STYLE.md` on `review`/`draft`/`editor` (Global Constraint 6); this is the only step that touches the network; run the tool as `.venv/bin/refereekit` or `source .venv/bin/activate` (`. .venv/bin/activate.fish` for fish) and then `refereekit`. Expected `--help` output (paste it):

```text
usage: refereekit [-h]
                  {ingest,verify,serve,draft,editor,mem-store,mem-recall,review,or-fetch,or-draft,or-responses} ...
```

End Part 1 with: *You can now run the [tutorial](tutorial.md).*

`## Part 2: model access and OpenReview`

- Extras: `.venv/bin/pip install -e ".[llm]"` (Anthropic SDK), `.venv/bin/pip install -e ".[openreview]"` (`openreview-py`), combined `".[llm,openreview]"`; `dev` is pytest for running the suite, not for reviewing.
- `### The three deployments` — a short table (deployment / install / variables the SDK reads / default model), then one subsection each, worked end to end and marked per the writing rules:
  - `#### anthropic` — `ANTHROPIC_API_KEY`; default model `claude-opus-4-8`; it is the default "only because it is the one a referee with an API key already has". *Not run while writing this page: needs an API key.*
  - `#### bedrock` — `.venv/bin/pip install "anthropic[bedrock]"` (the `llm` extra installs the SDK alone); `AWS_REGION`, `AWS_PROFILE`, read by the AWS SDK; `REFEREEKIT_BACKEND=bedrock`; default model `anthropic.claude-opus-5`; SSO profiles need `pip install "botocore[crt]"`. *Not run while writing this page: needs an AWS account.*
  - `#### vertex` — `.venv/bin/pip install "anthropic[vertex]"`; `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID`, `gcloud auth application-default login`; `REFEREEKIT_BACKEND=vertex`; **no confirmed default model** — refereekit refuses with `deployment 'vertex' has no confirmed default model; set REFEREEKIT_MODEL to the id you want to use` (paste it: `REFEREEKIT_BACKEND=vertex $RK draft --session work/tutorial`, exit 2, reproducible offline). *This path is documented from the SDK's code and has not been run.*
  - `#### Why the defaults name different model generations` — spec §4.3 wording: a default exists only where that id has been exercised against that deployment, because a fabricated id looks authoritative, gets copied into scripts, and fails at the provider with an error naming the model instead of the mistake.
- `### The attestation` — one paragraph: `REFEREEKIT_ZERO_RETENTION=1`; what it asserts depends on the deployment; link to `concepts/confidentiality.md`; do not repeat the table.
- `### Your .env` —

```bash
cp .env.template .env
# then edit .env, and load it:
source scripts/load-env.fish        # fish
set -a; . ./.env; set +a            # bash, zsh
```

State: refereekit reads only the environment and never parses `.env`; PowerShell users set the variables by hand; the loader prints `load-env: exported N variable(s): …` (names only, never values). Paste the loader's real output for a `.env` that sets only `REFEREEKIT_FAKE=1` — run (`--no-config` because the author's fish config changes directory on start):

```bash
printf 'REFEREEKIT_FAKE=1\n' > work/env-demo && fish --no-config -c 'cd /Users/tzuchi/Documents/Workspace/refereekit; source scripts/load-env.fish work/env-demo; echo "REFEREEKIT_FAKE=$REFEREEKIT_FAKE"'; rm -f work/env-demo
```

   Expected: `load-env: exported 1 variable(s): REFEREEKIT_FAKE` then `REFEREEKIT_FAKE=1`. On the page the reader's command is just `source scripts/load-env.fish` (it defaults to `.env`).
- `### OpenReview` — `OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD` in `.env`; an empty value counts as unset; link to `guides/openreview-review.md`.
- **Next** → `tutorial.md`, `guides/journal-review.md`, `reference/environment.md`.

- [ ] **Step 1: Run the reproducible blocks** (`--help`, the vertex refusal, the loader demo) and keep the outputs.
- [ ] **Step 2: Write the page** as above.
- [ ] **Step 3: Verify** — every command in Part 1 has been run in a fresh shell (`python3 -m venv work/venv-check && work/venv-check/bin/pip install -e . >/dev/null && work/venv-check/bin/refereekit --help | head -2 && rm -rf work/venv-check`) — Expected: the two `usage:` lines. LINKCHECK → `links ok`; PATHCHECK → nothing.
- [ ] **Step 4: Commit**

```bash
git add docs/install.md
git commit -m "docs: install, in two parts

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: `docs/tutorial.md`

The page the whole structure is built around. Verified to work as written (spec §4.4).

**Files:**
- Overwrite: `docs/tutorial.md`

- [ ] **Step 1: Run the tutorial exactly as the page will show it**

From the repo root, with FAKE set:

```bash
rm -rf work/tutorial
printf 'What does the paper study?\n\nminor revision\nPRX\nminor\n\n\n' | $RK review tests/fixtures/real_paper.pdf --session work/tutorial; echo "exit $?"
```

Expected output, verbatim:

```text
SUMMARY:
On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".
question> On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".  ⚠ CITATION FAILED: page (3); unquoted, not verified: page (2)
question> verdict (recommend)> venue> major/minor> section lengths (name=len, comma-sep; blank=default)> editor-answer key (blank to end)> review complete: work/tutorial/ours/report.txt, work/tutorial/ours/editor.txt (2 flag(s))
exit 0
```

Then the tour:

```bash
ls work/tutorial work/tutorial/ours
python3 -m json.tool work/tutorial/state.json
cat work/tutorial/ours/report.txt
$RK draft --session work/tutorial
$RK verify --session work/tutorial --kind quote --anchor 1 --text "a finite set of nodes"; echo "exit $?"
$RK verify --session work/tutorial --kind quote --anchor 3 --text "words that are not on that page"; echo "exit $?"
$RK verify --session work/tutorial --kind page --anchor 2 --text "model"; echo "exit $?"
```

Expected: `doc.json index.html ours state.json` / `editor.txt report.txt`; the JSON with `qa_count 1`, the two claims, the verdict; the report is the fake string; `report: wrote 124 chars, 1 flag(s)` + `  FLAG page (3): not in verified pool`; `PASS: found on page 1`/0; `FAIL: not found on page 3`/1; `FLAG: page 2 exists; no quotation to verify: 1 words, need 4`/3.

And `serve` (Global tooling) → `serving work/tutorial at http://127.0.0.1:8888/`, `HTTP 200`.

- [ ] **Step 2: Write the page**

Overwrite `docs/tutorial.md` with these sections:

1. H1, then: *This needs [part 1 of the install](install.md#part-1-get-it-running) and nothing else: no API key, no account, and after the install no network.* One paragraph: what will happen (a review of the shipped fixture, the author's own public paper, with a fake backend that returns a fixed string instead of calling a model — so the summary, every answer, the report and the letter will all be that same string; what is real is everything refereekit does *around* the model: ingesting the PDF, verifying every citation, building the claim pool, gating the drafts).
2. `## 1. Set up the fake backend` — the two `export` lines from FAKE, and one paragraph on why that string: three citations, one per sentence, chosen to come back PASS, FLAG and FAIL.
3. `## 2. Run the review` — `refereekit review tests/fixtures/real_paper.pdf --session work/tutorial`, then the **interactive transcript**, reconstructed from the run in Step 1 with typed input on its own line after each prompt (this is what a terminal shows; explain that a blank line ends the Q&A loop and the editor loop):

```text
SUMMARY:
On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".
question> What does the paper study?
On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".  ⚠ CITATION FAILED: page (3); unquoted, not verified: page (2)
question>
verdict (recommend)> minor revision
venue> PRX
major/minor> minor
section lengths (name=len, comma-sep; blank=default)>
editor-answer key (blank to end)>
review complete: work/tutorial/ours/report.txt, work/tutorial/ours/editor.txt (2 flag(s))
```

   Under it, a paragraph per stage: **the summary**; **the Q&A loop and what an anchor is** (a `p. N` or `Eq. (N)` in an answer; each is checked against the PDF: `"a finite set of nodes"` on p. 1 PASSed and entered the pool, `Page 2` carried no quotation so it is FLAG — unverified but on a page that exists, and it entered the pool too — and the p. 3 quotation FAILed and stays out; link `concepts/verification.md`); **the verdict gate** (three typed answers — the verdict is your prose, an input to the draft); **the section-length gate** (blank accepts defaults; `summary=short` form); **the editor-answer gate** (key, then answer; blank ends).
   Then the piped one-liner, labelled as the same run for scripts, with its real output from Step 1 and the sentence that it looks jammed together only because the prompts have no newline.
4. `## 3. What landed` — the `ls`, the `state.json` (paste), `report.txt` (paste, and the sentence that with a real model this is a report), `refereekit draft --session work/tutorial` to see the flag lines (paste; explain `not in verified pool`), then `refereekit serve --session work/tutorial` (paste the line; open the URL; MathJax loads from a CDN — the only network request, and not by refereekit).
5. `## 4. Verify a quotation by hand` — the three `verify` commands with outputs and exit codes; `echo $?` (bash/zsh) or `echo $status` (fish).
6. `## Next` — `install.md#part-2-model-access-and-openreview` for a real run; `guides/journal-review.md` for the full journey; `concepts/verification.md` for what PASS promises.

- [ ] **Step 3: Verify** — re-run Step 1 from `rm -rf work/tutorial` and diff every pasted block against the fresh output (character-exact); confirm every `--session` in the page is `work/tutorial`; LINKCHECK → `links ok`; PATHCHECK → nothing.

- [ ] **Step 4: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: the offline tutorial, verified as written

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: `docs/guides/journal-review.md`

**Files:**
- Overwrite: `docs/guides/journal-review.md`

**Content (spec §4.5), as a narrative in this order, failure modes inline where they would occur:**

1. **Before you run**: the venue's rule (link `../before-you-start.md`); model access set up (link `../install.md#part-2-model-access-and-openreview`); `REFEREEKIT_ZERO_RETENTION=1` and what it asserts (link `../concepts/confidentiality.md`).
2. **The PDF and the session**: put the PDF under `work/` too; `--session work/<short-name>`, one paper per session; why `work/` (`../concepts/confidentiality.md`).
3. **`--venue`**: two effects — the policy gate (paste the NeurIPS refusal from Step 1 below, exit 2, "before the PDF is opened") and venue memory (without it, no `memory.db`, no recall). `--db work/memory.db` if you want notes to carry across papers, because the default `<session>/memory.db` is per-session (link `your-voice.md`).
4. **The run**: `refereekit review work/<name>/paper.pdf --session work/<name> --venue PRX --db work/memory.db` — *Not run while writing this page: needs an API key.* Then the gates in order, each one sentence, pointing at the tutorial for the transcript; a real question is a considered one — link `review-spec.md` for the non-interactive form. Failure modes inline: `refusing to send: backend is not marked zero_retention` (attestation unset); `unknown deployment 'x'; expected one of anthropic, bedrock, vertex` (typo, refused rather than defaulted; paste from `REFEREEKIT_BACKEND=foo $RK draft --session work/tutorial`); a `Style guide not found` (non-editable install or `--style` typo).
5. **Read the flags**: `review complete: … (N flag(s))` is a count; `refereekit draft --session work/<name>` re-drafts and prints each `FLAG page (N): reason`; the two reasons and what to do about each (`not in verified pool` → the draft cited something the Q&A never established: ask about it, or cut it; `failed re-verification` → the wording no longer matches the PDF: check by hand). A draft with no pool and no flags is a draft that cited nothing.
6. **Edit the drafts**: `ours/report.txt`, `ours/editor.txt` are starting points; `--length` and `--answers` on `draft`/`editor` to regenerate parts (`../reference/cli.md`); the style guide (`your-voice.md`).
7. **Afterwards**: `mem-store` a note about the venue in your own words — the `mem-store … --db work/memory.db` command from Step 1 with its `stored note for PRX` output; link `your-voice.md` for what the guard rejects.
8. **See also** → `review-spec.md`, `your-voice.md`, `piecemeal.md`, `../troubleshooting.md`.

- [ ] **Step 1: Run the reproducible blocks** — all offline; `work/tutorial` as built by `rm -rf work/tutorial && printf 'What does the paper study?\n\nminor revision\nPRX\nminor\n\n\n' | $RK review tests/fixtures/real_paper.pdf --session work/tutorial >/dev/null` with FAKE set:

```bash
REFEREEKIT_FAKE=1 $RK review tests/fixtures/real_paper.pdf --session work/neurips --venue NeurIPS.cc/2026/Conference </dev/null; echo "exit $?"; rm -rf work/neurips
env -u REFEREEKIT_FAKE -u ANTHROPIC_API_KEY $RK draft --session work/tutorial; echo "exit $?"
env -u REFEREEKIT_FAKE REFEREEKIT_BACKEND=foo $RK draft --session work/tutorial; echo "exit $?"
REFEREEKIT_FAKE=1 REFEREEKIT_STYLE=/nonexistent/STYLE.md $RK draft --session work/tutorial; echo "exit $?"
$RK draft --session work/tutorial; echo "exit $?"
rm -f work/memory.db; $RK mem-store --session work/tutorial --venue PRX --kind verdict --text "PRX: lean accept-after-major on approximate-but-validated theory" --db work/memory.db; echo "exit $?"
```

Expected: `review failed: NeurIPS.cc/2026/Conference prohibits sending the submission to an outside model, so this command will not send it. Use the venue's own review interface. If this rule has changed, override it with a REFEREEKIT_VENUE_POLICY file containing:  [venues]` + `    "NeurIPS.cc/2026/Conference" = { llm = true }`/2; `error: refusing to send: backend is not marked zero_retention`/2; `error: unknown deployment 'foo'; expected one of anthropic, bedrock, vertex`/2; `error: Style guide not found: /nonexistent/STYLE.md`/2; `report: wrote 124 chars, 1 flag(s)` + `  FLAG page (3): not in verified pool`/0; `stored note for PRX`/0.

- [ ] **Step 2: Write the page.**
- [ ] **Step 3: Verify** — LINKCHECK → `links ok`; PATHCHECK → nothing; every unverified block carries its italic line.
- [ ] **Step 4: Commit**

```bash
git add docs/guides/journal-review.md
git commit -m "docs: the journal review journey

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: `docs/guides/review-spec.md`

**Files:**
- Overwrite: `docs/guides/review-spec.md`

**Content (spec §4.7; source `refereekit/spec.py`, `docs/review-spec.example.toml`):**

1. **Why a spec**: the gates prompt for typed answers, and a real verdict is prose drafted over days; `--spec` supplies everything, so a review runs with no terminal interaction (`spec.py:1-15`).
2. **Format**: `questions` — array of strings, required, non-empty (`spec.py:45-50`); `[verdict]` — `recommend`, `venue`, `major_minor`, all required (`spec.py:22, 52-57`); `[section_lengths]` optional; `[editor_answers]` optional, keys as the form labels them; top-level `venue` optional and **falls back to `[verdict].venue`** (`spec.py:64`), so a verdict naming the venue drives the policy gate and memory without the top-level key. Show a minimal spec inline (invented text, no manuscript words) and link `../review-spec.example.toml` for the full annotated one.
3. **Why TOML**: `tomllib` is standard library from 3.11; triple-quoted strings keep a thousand-word verdict readable; JSON would put it on one escaped line; YAML would be a dependency (`spec.py:8-11`).
4. **Parsed first**: before the backend is built and before the PDF is opened, so a spec that cannot drive the run fails while nothing has been sent (`cli.py:207-210`). Paste the three errors, reproducible offline:

```bash
printf 'questions = []\n' > work/bad.toml && $RK review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/bad.toml; echo "exit $?"
printf 'questions = ["q"]\n' > work/bad.toml && $RK review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/bad.toml; echo "exit $?"
printf 'questions = ["q"]\n[verdict]\nrecommend = "x"\n' > work/bad.toml && $RK review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/bad.toml; echo "exit $?"
```

   Expected: `review failed: work/bad.toml: 'questions' is empty; a review that asks nothing leaves an empty claim pool and the draft would have nothing verified to cite`/2; `review failed: work/bad.toml: no 'verdict' table`/2; `review failed: work/bad.toml: verdict is missing venue, major_minor`/2. Then `rm -f work/bad.toml`.
5. **A real spec is confidential**: it quotes the manuscript; write it beside its session under `work/`, never in the repository; it is the record of what you asked and makes a review re-runnable.
6. **A complete offline run from a spec**: write `work/spec-demo/review.toml` with `questions = ["What does the paper study?"]`, `[verdict]` `recommend = "minor revision"`, `venue = "PRX"`, `major_minor = "minor"`; run with FAKE set: `$RK review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/spec-demo/review.toml` — Expected: the same three output lines as the tutorial's piped run but with no prompts echoed (`review complete: work/spec-demo/ours/report.txt, work/spec-demo/ours/editor.txt (2 flag(s))`); paste it.
7. **See also** → `journal-review.md`, `../reference/cli.md`, `../review-spec.example.toml`.

- [ ] **Step 1: Run the blocks in items 4 and 6; keep outputs.**
- [ ] **Step 2: Write the page.**
- [ ] **Step 3: Verify** — LINKCHECK → `links ok`; PATHCHECK → nothing; `rm -rf work/spec-demo work/bad.toml`.
- [ ] **Step 4: Commit**

```bash
git add docs/guides/review-spec.md
git commit -m "docs: driving a review from a spec

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: `docs/guides/your-voice.md`

**Files:**
- Overwrite: `docs/guides/your-voice.md`

**Content (spec §4.8; sources `style/STYLE.md`, `refereekit/style.py`, `cli.py:162,178,228,359`, `memory.py`, `guard.py`):**

1. **The style guide**: `style/STYLE.md` is the default; `--style path` beats `REFEREEKIT_STYLE` beats the default; it is pasted into every drafting prompt as the voice guide (`drafts.py:80-83`). What belongs in one (how you structure a report, your verdict vocabulary, sentence habits) and what must never (raw report text, manuscript identifiers, other papers' content) — because the file is committable and travels with the repository. Point at the shipped `style/STYLE.md` as an example, without pasting it.
2. **Venue memory, precisely**:
   - `mem-store --session work/<name> --venue PRX --kind verdict --text "…" [--db path]` — `--session` is required so the note is checked against that manuscript; `--db` defaults to `<session>/memory.db`.
   - `mem-recall --venue PRX --db path [--limit 20]` — `--db` required; deduplicated by exact text, newest first (`memory.py:37-44`); a `--db` path that does not exist is created empty and prints nothing, exit 0 (a typo is silent).
   - `review` and `or-draft` default to `<session>/memory.db` and open no store unless a venue is known — so **by default memory is per-session**; to carry notes across papers pass the same `--db work/memory.db` to `mem-store`, `review` and `or-draft`, every time. `draft` and `editor` never read memory.
   - Notes reach the prompt as `PRIOR NOTES` (`drafts.py:66-71`).
3. **What the guard rejects**: any verbatim fragment of the session's manuscript — a short exact match, an eight-word run, or more than one shared eight-word window (`guard.py:29-75`); against an empty document it refuses outright. Write notes about the venue and your habits, in your own words.
4. **See also** → `journal-review.md`, `../reference/cli.md`, `../concepts/confidentiality.md`.

- [ ] **Step 1: Run the memory blocks on `work/tutorial`** (build TUTSESSION first):

```bash
rm -f work/memory.db
$RK mem-store --session work/tutorial --venue PRX --kind verdict --text "PRX: lean accept-after-major on approximate-but-validated theory" --db work/memory.db; echo "exit $?"
$RK mem-store --session work/tutorial --venue PRX --kind quote --text "a finite set of nodes" --db work/memory.db; echo "exit $?"
$RK mem-recall --venue PRX --db work/memory.db; echo "exit $?"
```

Expected: `stored note for PRX`/0; `mem-store failed: input is a verbatim manuscript fragment (short verbatim manuscript fragment)`/2; `[PRX/verdict] PRX: lean accept-after-major on approximate-but-validated theory`/0.

- [ ] **Step 2: Write the page** with the three outputs pasted under item 2 and 3.
- [ ] **Step 3: Verify** — LINKCHECK → `links ok`; PATHCHECK → nothing.
- [ ] **Step 4: Commit**

```bash
git add docs/guides/your-voice.md
git commit -m "docs: the style guide and venue memory

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: `docs/guides/piecemeal.md`

**Files:**
- Overwrite: `docs/guides/piecemeal.md`

**Content (spec §4.9):** the tools alone, for a referee writing by hand. One section each, task-first (why you would reach for it), then the command, then the pasted output:

1. `ingest` then `verify` — check a single quotation against a page: `refereekit ingest work/paper.pdf --session work/<name>` (paste the fixture run: `ingested: 9 pages, 20 equations`), then three `verify` calls with outputs and exit codes — on `work/ref`: `--kind quote --anchor 1 --text "a finite set of nodes"` → `PASS: found on page 1`/0; `--kind quote --anchor 3 --text "words that are not on that page"` → `FAIL: not found on page 3`/1; `--kind page --anchor 2 --text "model"` → `FLAG: page 2 exists; no quotation to verify: 1 words, need 4`/3; what `--kind` accepts (`quote`/`page`, `equation`, `figure`); use the exit code in a script.
2. `serve` — read the rendered Q&A page; it exists only after `review` (after `ingest` alone the URL is a 404); the printed line; Ctrl-C to stop; the port moves if busy.
3. `draft` and `editor` against a session built by other means — they need `doc.json`; they take no `--db` and read no memory; they do not refuse an empty pool, they flag every anchor instead. Paste `refereekit draft --session work/ref` with FAKE set on the ingest-only `work/ref` session from Task 2 (recreate with `rm -rf work/ref && $RK ingest tests/fixtures/real_paper.pdf --session work/ref` if missing). Expected, verbatim — every anchor is flagged because the pool is empty, in the order the anchors are extracted (quoted citations first, then bare pointers):

```text
report: wrote 124 chars, 3 flag(s)
  FLAG page (1): not in verified pool
  FLAG page (3): not in verified pool
  FLAG page (2): not in verified pool
```

   Contrast it with the same command on `work/tutorial` (1 flag) to show what a pool does. Then `--length name=value` and `--answers key=value`, pointing at the reference.
4. **See also** → `../reference/cli.md` (what each accepts), `../concepts/verification.md`, `../tutorial.md`.

- [ ] **Step 1: Run the blocks** — recreate `work/ref` with the `ingest` command in item 3, build TUTSESSION for the contrast, run every command in items 1–3 with FAKE set; keep outputs; confirm the three-flag output in item 3 from the real run.
- [ ] **Step 2: Write the page.**
- [ ] **Step 3: Verify** — LINKCHECK → `links ok`; PATHCHECK → nothing.
- [ ] **Step 4: Commit**

```bash
git add docs/guides/piecemeal.md
git commit -m "docs: the tools on their own

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: `docs/guides/openreview-review.md`

Every block on this page that touches OpenReview is unverified and says so (Global writing rules). The offline-reproducible errors are pasted.

**Files:**
- Overwrite: `docs/guides/openreview-review.md`

**Content (spec §4.6; sources `refereekit/cli.py:238-442`, `refereekit/openreview/*.py`):**

1. **Setup**: `.venv/bin/pip install -e ".[openreview]"`; `OPENREVIEW_USERNAME`/`OPENREVIEW_PASSWORD` in `.env` (never a flag — shell history and the process table; an empty value is rejected like an absent one); paste `error: set OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD` from `env -u OPENREVIEW_USERNAME -u OPENREVIEW_PASSWORD $RK or-fetch --venue X --session work/or-demo`, exit 2; the venue id form `ICLR.cc/2026/Conference` (`no venue …; check the venue id` otherwise).
2. **Find your assignments**: `refereekit or-fetch --venue ICLR.cc/2026/Conference --session work/iclr` — no `--number` lists them (`  <number>  <title>`), names unreadable ones (usually withdrawn/desk-rejected), and ends `Fetch one with: --number <N>`. *Not run while writing this page: needs an OpenReview account.*
3. **The four commands and why four**: `or-fetch --number` (paper + form), `review` (the pool, with you), `or-draft` (prose fields from the pool), `or-responses` (what came back). Show the sequence with `--session work/iclr-42` on every line and `--venue` on `review` (the session records it, so `--venue` may be omitted, but say both). All four blocks marked unverified except the offline errors.
4. **What `or-fetch --number` writes and prints**: `paper.pdf`, `doc.json`, `state.json` (`venue`, `number`, `forum`, `invitation_id`), `form.json`, `theirs/`; `fetched submission 42: 9 pages`; the form is best-effort — before the review stage opens, `no review form at ICLR.cc/2026/Conference/Submission42/-/Official_Review (<reason>); skipping form.json` and exit 0; the discussion is best-effort — `no replies yet; theirs/ left empty` or `could not read the discussion …`; a later `or-fetch --number 42` into the same session picks both up. `theirs/: 2 new, 0 unchanged, 1 held back` and the held-back paragraph (ownership could not be confirmed; named on stdout; check by hand on the forum). A non-PDF download is refused before `paper.pdf` exists; a malformed PDF can leave `paper.pdf` behind on exit 2 — read the message.
5. **One session, one paper**: `error: session work/iclr-42 holds submission 42, not 43; use a fresh --session directory for a different paper`; re-fetching the *same* number is how you pick up a rebuttal — and it re-downloads and re-ingests the PDF, so `paper.pdf`/`doc.json` become the current version while the claims in `state.json` were verified against the earlier one; a revised manuscript can turn a verified quotation into `failed re-verification` on the next `or-draft`.
6. **`or-draft`**: needs `form.json` and a reviewed session. Everything below is reproducible offline by building a demo session from the tutorial session and a shipped fixture form — say on the page that the form comes from a fixture, not a fetch, and that a real `form.json` is written by `or-fetch`:

```bash
rm -rf work/tutorial work/or-demo
printf 'What does the paper study?\n\nminor revision\nPRX\nminor\n\n\n' | $RK review tests/fixtures/real_paper.pdf --session work/tutorial >/dev/null
mkdir -p work/or-demo && cp work/tutorial/doc.json work/or-demo/
.venv/bin/python -c "import json; from refereekit.openreview import form as f; open('work/or-demo/form.json','w').write(f.to_json(f.parse_form(json.load(open('tests/fixtures/openreview_default_form.json')))))"
$RK or-draft --session work/tutorial; echo "exit $?"                     # no form.json
$RK or-draft --session work/or-demo; echo "exit $?"                      # form, no pool
$RK or-draft --session work/or-demo --length summary; echo "exit $?"     # malformed
cp work/tutorial/state.json work/or-demo/                                # now it has a pool
$RK or-draft --session work/or-demo --length nosuch=short; echo "exit $?"  # unknown field
$RK or-draft --session work/or-demo; echo "exit $?"
cat work/or-demo/ours/openreview.md
```

   Expected, in order: `error: no form.json; run or-fetch --number first`/2; `error: no verified claims in this session; run refereekit review work/or-demo/paper.pdf --session work/or-demo first`/2; `error: --length takes name=value, e.g. --length summary=short`/2; `error: --length names no field in this form: nosuch`/2; then the successful run:

```text
openreview: 2 prose field(s) drafted, 1 flag(s)
  FLAG page (3): not in verified pool
to fill in yourself:
  rating                   (1-10)
  confidence               (1-5)
```

   and `ours/openreview.md` — paste it: an H1 with the invitation id, one `## <field>` per field in the form's order with the venue's instruction as an HTML comment, the fake string under `title` and `review`, and `(fill in yourself. options: …)` under `rating` and `confidence`; `ours/openreview.json` maps every field name to its value, blanks as `""`. Then repeat the successful run with the ICLR fixture (`tests/fixtures/openreview_iclr_form.json` in the same one-liner) — Expected `openreview: 4 prose field(s) drafted, 1 flag(s)` and eight `to fill in yourself` lines (`soundness (1-4)`, `presentation`, `contribution`, `rating (3-8)`, `confidence`, `flag_for_ethics_review`, `code_of_conduct`, `supplementary (file)`); the four drafted fields are `summary`, `strengths`, `weaknesses` **and `confidential_comment`**, which is the demonstration of the rule below.

   State: **ratings and every fixed-choice field are never filled**, because substring verification cannot justify a soundness of 3 over a 4; the form is discovered at runtime from the invitation and a field is classified by whether it has fixed choices, not by its name — so **every free-text field is drafted**, including a confidential comment to the area chairs and any LLM-usage or self-assessment textbox a venue adds; those you rewrite by hand, and a disclosure box must be your own words (link `../before-you-start.md`). `--length summary=short` per field; `--db work/memory.db` mirrors `review`. `ours/openreview.md` is for reading and pasting into the web form.
7. **`or-responses`**: reads all of `theirs/` as what came back and `ours/openreview.md` (else `ours/report.txt`) as yours; writes `ours/response-analysis.txt`; no rating, no recommendation; paste `error: no received notes in theirs/; nothing to analyze` from `$RK or-responses --session work/or-demo`; its last line notes that claims about a *revised* manuscript cannot be checked against `doc.json`.
8. **Read-only, and the sandbox**: no `post_note_edit` in the package (`refereekit/openreview/client.py:8-9`); output is local for you to paste; `--baseurl https://devapi2.openreview.net` for a dry run against the sandbox.
9. **Confidentiality**: a fetched submission is manuscript text under `work/`; `form.json` is venue configuration; `openreview.md`, `openreview.json`, `response-analysis.txt` are derived and never committed; the venue's own LLM rule comes first (`../before-you-start.md`).
10. **See also** → `../reference/cli.md`, `../reference/session.md`, `../troubleshooting.md`, `journal-review.md`.

- [ ] **Step 1: Run the offline blocks** (items 1, 6, 7); build and later remove `work/or-demo`.
- [ ] **Step 2: Write the page.**
- [ ] **Step 3: Verify** — every OpenReview-touching block has the italic unverified line; LINKCHECK → `links ok`; PATHCHECK → nothing; `rm -rf work/or-demo`.
- [ ] **Step 4: Commit**

```bash
git add docs/guides/openreview-review.md
git commit -m "docs: reviewing on OpenReview

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: `docs/troubleshooting.md`

**Files:**
- Overwrite: `docs/troubleshooting.md`

**Content (spec §4.15):** H1; one sentence (find your message; every row says what it means and what to do; messages go to stderr with the prefixes `error:`, `review failed:`, `mem-store failed:`, `mem-recall failed:`); then a table with **Message · Cause · Fix** columns, one row per line of the spec §4.15 table — reproduce every offline-reproducible message with the commands already run in Tasks 6, 7, 9, 10, 11, 13 and copy the string exactly; for network-only messages (`openreview login failed for …`, `no venue …`, `submission N is not assigned to you at …`, `session … holds submission N`, `could not confirm these are not your own review`) copy the string from `refereekit/openreview/client.py:55, 99-101, 125` and `refereekit/cli.py:268-270, 326-330`. Group rows under `##` headings: **Install and model access**, **Venue and confidentiality**, **Review and drafting**, **Memory**, **OpenReview**, **Verification surprises** (the two non-error rows: an equation cites correctly but FAILs; a correct quotation FLAGs).

Then the standalone paragraph, in the spec's words: **an exit 2 does not guarantee an empty session directory** — `or-fetch` validates what it can before writing and rejects a non-PDF download before `paper.pdf` is created, but a file that begins with `%PDF` and is then found malformed leaves `paper.pdf` on disk; read the message rather than the presence of files (`refereekit/cli.py:277-283, 332-341`).

**See also** → `reference/cli.md`, `concepts/verification.md`, `guides/openreview-review.md`.

- [ ] **Step 1: Reproduce every offline message and collect the network-only ones from source**

With `work/tutorial` built (`rm -rf work/tutorial && REFEREEKIT_FAKE=1 REFEREEKIT_FAKE_TEXT='On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".' sh -c "printf 'What does the paper study?\n\nminor revision\nPRX\nminor\n\n\n' | $RK review tests/fixtures/real_paper.pdf --session work/tutorial" >/dev/null`), run each and copy the string exactly:

```bash
REFEREEKIT_FAKE=1 REFEREEKIT_STYLE=/nonexistent/STYLE.md $RK draft --session work/tutorial               # Style guide not found
env -u REFEREEKIT_FAKE -u ANTHROPIC_API_KEY $RK draft --session work/tutorial                             # refusing to send
env -u REFEREEKIT_FAKE REFEREEKIT_BACKEND=foo $RK draft --session work/tutorial                            # unknown deployment
env -u REFEREEKIT_FAKE REFEREEKIT_BACKEND=vertex $RK draft --session work/tutorial                         # no confirmed default model
REFEREEKIT_FAKE=1 $RK review tests/fixtures/real_paper.pdf --session work/neurips --venue NeurIPS.cc/2026/Conference </dev/null; rm -rf work/neurips   # venue refusal
$RK mem-store --session work/tutorial --venue PRX --kind quote --text "a finite set of nodes" --db work/memory.db   # verbatim fragment
printf 'questions = []\n' > work/bad.toml && $RK review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/bad.toml
printf 'questions = ["q"]\n' > work/bad.toml && $RK review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/bad.toml
printf 'questions = ["q"]\n[verdict]\nrecommend = "x"\n' > work/bad.toml && $RK review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/bad.toml; rm -rf work/bad.toml work/spec-demo
env -u OPENREVIEW_USERNAME -u OPENREVIEW_PASSWORD $RK or-fetch --venue X --session work/or-demo             # set OPENREVIEW_USERNAME …
$RK or-draft --session work/tutorial                                                                       # no form.json
mkdir -p work/or-demo && cp work/tutorial/doc.json work/or-demo/ && .venv/bin/python -c "import json; from refereekit.openreview import form as f; open('work/or-demo/form.json','w').write(f.to_json(f.parse_form(json.load(open('tests/fixtures/openreview_default_form.json')))))"
$RK or-draft --session work/or-demo                                                                        # no verified claims
$RK or-draft --session work/or-demo --length summary                                                       # --length takes name=value
cp work/tutorial/state.json work/or-demo/ && $RK or-draft --session work/or-demo --length nosuch=short     # --length names no field
$RK or-responses --session work/or-demo; rm -rf work/or-demo                                               # no received notes
REFEREEKIT_FAKE=1 REFEREEKIT_FAKE_TEXT='On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".' $RK draft --session work/tutorial   # FLAG … not in verified pool
$RK verify --session work/tutorial --kind equation --anchor 18 --text ""                                   # outside the vouched run
$RK verify --session work/tutorial --kind page --anchor 2 --text "model"                                   # under four words → FLAG
```

Network-only rows come from source, copied exactly: `openreview login failed for <username>` (`refereekit/openreview/client.py:55`), `no venue <venue>; check the venue id, e.g. ICLR.cc/2027/Conference` (`client.py:99-101`), `submission N is not assigned to you at <venue>` (`client.py:125`), `session <dir> holds submission N, not M; use a fresh --session directory for a different paper` (`refereekit/cli.py:268-270`), `could not confirm these are not your own review, so they were not stored in theirs/:` (`cli.py:326-330`), `no review form at …; skipping form.json` (`cli.py:297-299`), `openreview support requires: pip install -e ".[openreview]"` (`client.py:41-42`; reproducible only with the extra uninstalled — do not uninstall it), and the two `failed re-verification` / re-fetch rows from `refereekit/drafts.py:110-111`.

- [ ] **Step 2: Write the page.**
- [ ] **Step 3: Verify** — every message string is grep-able in `refereekit/` (`grep -rn "<distinctive words>" refereekit/`) or was pasted from a run; LINKCHECK → `links ok`; PATHCHECK → nothing.
- [ ] **Step 4: Commit**

```bash
git add docs/troubleshooting.md
git commit -m "docs: troubleshooting, message to cause to fix

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 15: `docs/before-you-start.md`

**Files:**
- Overwrite: `docs/before-you-start.md`

**Content (spec §4.2), four sections in this order, and nothing else:**

1. `## Your venue's rules come first, and they differ` — Two checked examples, both with URL and "as of 2026-08-15":
   - **NeurIPS 2025** prohibits it. Quote from the "NeurIPS 2025 LLM Policy for Reviewers", `https://neurips.cc/Conferences/2025/LLM`: "You must keep everything relating to the review process confidential. … Do not talk about or share submissions with anyone or any LLMs." Zero-retention API terms create no exception: the prohibition is on sharing at all, not on retention.
   - **ICLR 2026** permits it with disclosure. Quote from "The Use of Large Language Models (LLMs)" in the ICLR 2026 Reviewer Guide, `https://iclr.cc/Conferences/2026/ReviewerGuide`: "The use of LLMs is allowed as a general-purpose writing assistance tool" and "we mandate that reviewers disclose the use of LLMs in their reviews. The review form will include a field to specify how you used LLMs, if at all." Note that ICLR 2027's guide was not yet published on that date.
   - Most venues are silent; the judgment is yours; these are examples the author checked on that date, not a table refereekit maintains — check your venue's current page.
2. `## refereekit knows about one prohibition and cannot discover others` — the built-in table has one entry, NeurIPS, matched against the bare name and the OpenReview id and against every year of it, so a later year's change is an override you write; `REFEREEKIT_VENUE_POLICY` with the three-line TOML example from `refereekit/policy.py:20-22`; unlisted venues are permitted, because refusing the unknown would make the tool useless for the long tail of journals; keeping it current is your job. Paste the refusal as what it looks like when the gate fires — run `REFEREEKIT_FAKE=1 $RK review tests/fixtures/real_paper.pdf --session work/neurips --venue NeurIPS.cc/2026/Conference </dev/null; echo "exit $?"; rm -rf work/neurips` — Expected: `review failed: NeurIPS.cc/2026/Conference prohibits sending the submission to an outside model, so this command will not send it. Use the venue's own review interface. If this rule has changed, override it with a REFEREEKIT_VENUE_POLICY file containing:  [venues]` then `    "NeurIPS.cc/2026/Conference" = { llm = true }`, `exit 2`.
3. `## Confidentiality is your obligation` — a submission goes only to a backend you have configured for zero-retention, and never into a repository; author responses count (`or-responses` sends them on the same path); link `concepts/confidentiality.md`.
4. `## What refereekit does not do` — spec §4.2 item 4 verbatim in substance: it does not write your review; the verdict is your prose, an input; every fixed-choice field comes back empty; `or-draft` refuses a session with neither claims nor a verdict, naming the `review` command; `review`, `draft` and `editor` do not refuse an empty pool — they draft and flag every anchor `not in verified pool`, so a draft with no pool and no flags is a draft that cited nothing, not one that was checked; this is the honest framing and the strongest argument for the design.
5. **Next** → `install.md#part-1-get-it-running` and `tutorial.md` (to see it work), or `install.md` and a guide.

- [ ] **Step 1: Re-check the two sources today** — fetch each URL (WebFetch, or `firecrawl scrape "<url>" --only-main-content`) and confirm the quoted sentences are present verbatim; if a page has changed, quote what it now says and update the "as of" date; if a page is unreachable, keep the quote, keep the 2026-08-15 date, and add "(page not reachable when re-checked on <date>)".
- [ ] **Step 2: Write the page.**
- [ ] **Step 3: Verify** — LINKCHECK → `links ok`; PATHCHECK → nothing; both URLs and both dates present (`grep -c "as of 2026" docs/before-you-start.md` ≥ 2).
- [ ] **Step 4: Commit**

```bash
git add docs/before-you-start.md
git commit -m "docs: before you start — venue rules, confidentiality, and what the tool will not do

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 16: `docs/README.md`, the root `README.md`, and `QUICKSTART.md`

**Files:**
- Overwrite: `docs/README.md`
- Overwrite: `README.md`
- Delete: `QUICKSTART.md`

- [ ] **Step 1: Write `docs/README.md`**

```markdown
# refereekit documentation

refereekit is a command-line toolkit for refereeing a paper. It ingests the
submitted PDF, verifies every page, equation and figure anchor a draft cites
against that PDF, and drafts a referee report and an editor letter — in a voice
guide you supply, from claims that verified — for you to edit. It does not
write your review: the verdict is yours, and is an input to drafting rather
than an output of it. A manuscript under review goes only to a model backend
you have attested runs zero-retention, and never into a repository.

## Which path are you on?

| You are… | Read, in order |
|---|---|
| Evaluating the tool | [Before you start](before-you-start.md) → [Install, part 1](install.md#part-1-get-it-running) → [Tutorial](tutorial.md) |
| Reviewing for a journal | [Before you start](before-you-start.md) → [Install](install.md) → [Reviewing for a journal](guides/journal-review.md) |
| Reviewing on OpenReview | [Before you start](before-you-start.md) → [Install](install.md) → [Reviewing on OpenReview](guides/openreview-review.md) |
| Something failed | [Troubleshooting](troubleshooting.md) → [Command reference](reference/cli.md) |
| Deciding whether to trust it | [What verification means](concepts/verification.md) → [Confidentiality](concepts/confidentiality.md) |

## Everything else

| Page | For |
|---|---|
| [Driving a review from a spec](guides/review-spec.md) | non-interactive runs |
| [Your voice](guides/your-voice.md) | the style guide and venue memory |
| [The tools on their own](guides/piecemeal.md) | ingest, verify, serve, draft, editor by hand |
| [Environment variables](reference/environment.md) | every variable, and who reads it |
| [The session directory](reference/session.md) | what lands where |
```

- [ ] **Step 2: Write the root `README.md`**

```markdown
# refereekit

A command-line toolkit for refereeing a paper. It ingests the submitted PDF,
verifies every page, equation and figure anchor a draft cites against that PDF,
and drafts a referee report and an editor letter — in a voice guide you supply,
from claims that verified — for you to edit. It does not write your review: the
verdict is yours, and is an input to drafting rather than an output of it.

**Confidentiality first.** A manuscript under review goes only to a model
backend you have attested runs zero-retention, and never into this repository —
see [docs/concepts/confidentiality.md](docs/concepts/confidentiality.md).

**Documentation:** start with [docs/before-you-start.md](docs/before-you-start.md),
then pick a reading path from the [docs index](docs/README.md). The tutorial
runs offline with no API key.

MIT — see [LICENSE](LICENSE).
```

- [ ] **Step 3: Delete `QUICKSTART.md`**

```bash
git rm QUICKSTART.md
```

Then confirm nothing links to it: `grep -rn "QUICKSTART" README.md docs --include=*.md | grep -v superpowers | grep -v internal` — Expected: nothing (spec and plan under `docs/superpowers/` may mention it; that is fine).

- [ ] **Step 4: Verify** — LINKCHECK → `links ok`; PATHCHECK → nothing; STUBCHECK → nothing; `git status --short` shows only the three intended paths (plus the unrelated `aaai-worth-reading/`).

- [ ] **Step 5: Commit**

```bash
git add docs/README.md README.md
git commit -m "docs: route readers from the README and the docs index; retire QUICKSTART

QUICKSTART.md is superseded by docs/tutorial.md, which covers the same
ground offline and is verified. The root README no longer duplicates install
or the confidentiality rule; both live once, under docs/ (spec §1, §5).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

(`git rm` already staged the deletion.)

---

### Task 17: Final verification and the defect report

**Files:** none modified unless a check fails.

- [ ] **Step 1: The whole-suite checks**

Run each; all must pass:

- TESTS → `354 passed` (spec §6.5).
- LINKCHECK → `links ok` (spec §6.6).
- PATHCHECK → nothing (spec §6.7).
- STUBCHECK → nothing.
- `git status --short` → only `?? aaai-worth-reading/`; nothing under `work/` is tracked: `git ls-files work | wc -l` → `0`.
- `git diff --stat main..HEAD -- . ':!docs' ':!README.md' ':!QUICKSTART.md' ':!.env.template' ':!AGENTS.md' ':!scripts' ':!refereekit/openreview/client.py' ':!tests/openreview_fakes.py' ':!tests/test_or_client.py'` → empty (no other file changed since `main`).
- Every page's first line is its H1 from the table: `head -1 docs/*.md docs/guides/*.md docs/reference/*.md docs/concepts/*.md`.
- Every unverified block is labelled: `grep -c "Not run while writing this page" docs/guides/openreview-review.md docs/install.md docs/guides/journal-review.md` — each ≥ 1.
- No third-party fact without a date: `grep -n "NeurIPS 2025\|ICLR 2026" docs/*.md docs/guides/*.md docs/concepts/*.md | grep -v "as of" ` — inspect any hit; each must be within a paragraph that carries the "as of" date.

- [ ] **Step 2: Re-run the tutorial one last time from clean and diff against the page**

Build TUTSESSION, then run every command block printed in `docs/tutorial.md` in order; every pasted output block matches character-for-character (compare with `diff <(…) <(…)` or by eye on the short blocks).

- [ ] **Step 3: Clean the scratch sessions**

`rm -rf work/tutorial work/ref work/ref2 work/spec-demo work/or-demo work/neurips work/memory.db` — they are ignored anyway, but leave the checkout as found.

- [ ] **Step 4: Report the known defects to the user (spec §7.1), verbatim from the spec, as the closing message of the plan run**

1. Non-editable install breaks the default style path (`_DEFAULT_STYLE`, `refereekit/cli.py:17`).
2. `or-draft` drafts every free-text field, including confidential comments and any LLM-usage disclosure textbox (`refereekit/openreview/fill.py:93`, `form.py:43`).
3. Re-fetching replaces `doc.json` without re-verifying `state.json`'s claims; `responses.py:8-9`'s note says `doc.json` "holds the version originally fetched", which is untrue after a re-fetch.
4. `pyproject.toml` has no `bedrock`/`vertex` extras.
5. `serve` has no error handling; a missing session serves 404s rather than exiting 2.

Plus anything new found while writing, each with the file and line and what was observed. Nothing is fixed in this branch.

- [ ] **Step 5: Hand back** — state the branch (`docs/user-docs`), the commit list (`git log --oneline main..HEAD`), the test result, and that the branch is ready for the finishing-a-development-branch decision.

---

## Self-review (done while writing this plan)

**Spec coverage:** §0 → Task 0. §2 → Global Constraints, checked in Tasks 7 (editable), 4/6 (`work/`), 15 (dated facts), 17. §3 tree → Task 1; §3.2 paths → Task 16. §4.1 → 16; §4.2 → 15; §4.3 → 7; §4.4 → 8; §4.5 → 9; §4.6 → 13; §4.7 → 10; §4.8 → 11; §4.9 → 12; §4.10 → 2; §4.11 → 3; §4.12 → 4; §4.13 → 5; §4.14 → 6; §4.15 → 14. §5 → Tasks 0, 1, 3, 16. §6.1 → every page task's Step 1 and Task 17 Step 2; §6.2 → Task 2 Step 3; §6.3 → Task 3 Step 1; §6.4 → the writing rules and Task 17; §6.5 → Task 0 Step 1 and Task 17; §6.6 → LINKCHECK per task; §6.7 → PATHCHECK per task. §7.1 → Task 17 Step 4.

**Placeholders:** none — every page task carries the facts, sources, commands and expected outputs, and every output quoted as "Expected" was produced by a real run on 2026-08-15 against the current tree.

**Consistency:** the fixed strings (`REFEREEKIT_FAKE_TEXT`, the H1s, `work/tutorial`, `work/memory.db`, `ICLR.cc/2026/Conference`) are the same in every task that uses them; the tutorial outputs quoted in Tasks 4, 5, 8, 12 come from the same run.
