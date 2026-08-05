# refereekit — Quickstart

Review a paper, end to end, with one command.

## 1. Install (once)

The repo ships without a virtual environment, so create one before running
refereekit or the tests:

    python -m venv .venv && .venv/bin/pip install -e ".[dev,llm]"

## 2. Review a paper

    export REFEREEKIT_ZERO_RETENTION=1          # confirms the LLM won't retain your manuscript
    export ANTHROPIC_API_KEY=sk-...             # your key

    refereekit review paper.pdf --session ./work/paperA --venue PRX

That's it. refereekit walks you through the whole review:

1. **Summarizes** the paper for you.
2. **Q&A** — ask it anything about the paper. Every *anchor* it cites — a page or
   equation number pointing into the PDF — is checked against the actual document;
   any anchor it can't verify is *flagged* (marked as unconfirmed) rather than
   trusted. Press **Enter on a blank line** to finish asking.
3. Asks your **verdict** (recommend / venue / major-or-minor).
4. Asks about **section lengths** (just press Enter to accept defaults).
5. Asks the **editor's questions** (type a letter like `a`, then your answer;
   blank to finish).

## 3. What you get

In `./work/paperA/`:

| File | What it is |
|------|------------|
| `ours/report.txt`  | Your referee report, in your writing voice |
| `ours/editor.txt`  | Your response letter to the editor |
| `index.html`  | The Q&A session with math rendered — open it in a browser |

Edit the drafts freely — they're a starting point in your voice, not a final answer.

## Try it first, offline (no key, no network)

    export REFEREEKIT_FAKE=1
    printf 'What is the main claim?\n\nminor\nPRX\nminor\n\n\n' | \
      refereekit review tests/fixtures/real_paper.pdf --session /tmp/try --venue PRX

Uses canned text instead of a real LLM, so you can see the flow before using it for real.

## Good to know

- **Your manuscript stays private.** The PDF's text goes *only* to the
  zero-retention LLM and your local `--session` folder. It is never committed
  to git, never sent anywhere else.
- **`--venue`** (e.g. `PRX`, `PRE`) lets refereekit recall your past style notes
  for that journal. Optional — leave it off and it just skips that.
- **Remembering your preferences:** after a review, save a note for next time —
      refereekit mem-store --session ./work/paperA --venue PRX --kind verdict \
          --text "PRX: lean accept-after-major on approximate-but-validated theory"
  It'll surface in future `--venue PRX` reviews.

---

Want the individual tools (ingest / verify a single quote / draft only / serve the
HTML) instead of the all-in-one flow? See **README.md**.
