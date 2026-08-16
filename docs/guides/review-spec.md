# Driving a review from a spec

`review` normally asks you questions at a terminal: what to ask the paper,
your verdict, the venue, how serious the revisions are, and what to tell
the editor. A spec answers every one of those gates from a TOML file
instead, so the whole review runs with nothing typed at a prompt. This
page covers the file's format, when refereekit reads it and what stops it
early, and a complete review run end to end from a spec, offline.

## Why a spec

`run_review` drives every one of its gates through a function called
`input_fn`, and by default that function is Python's own `input()` — built
for someone typing a line at a time. A real verdict is not typed once at a
prompt: it is prose you draft and redraft, and the questions you put to
the manuscript are worth writing down and rereading before you ask them.
None of that belongs at a terminal. `--spec` replaces `input_fn` with one
that reads every answer from a file instead, so the whole review runs with
nothing typed at all (`refereekit/spec.py:1-15`).

## Spec format

A spec is a TOML file with one required table and up to three further
keys.

- `questions` — an array of strings, required and non-empty. Each string
  is one turn of the question-and-answer loop, asked and checked in the
  order they are written (`refereekit/spec.py:45-50`).
- `[verdict]` — a table with three required keys, all of which must be
  present and non-empty: `recommend` (your recommendation, in your own
  words), `venue`, and `major_minor` (`refereekit/spec.py:22, 52-57`).
- `[section_lengths]` — optional. Per-section length overrides for the
  report, the same as `draft --length`.
- `[editor_answers]` — optional. Keys are whatever the editor's own form
  labels its questions, the same as `editor --answers`.
- a top-level `venue` key, optional. `[verdict].venue` is mandatory, so
  every spec that loads at all already names a venue; the top-level key
  exists only to let a different string win. When it is absent,
  `load_spec` falls back to `[verdict].venue` (`refereekit/spec.py:64`) —
  so naming the venue once, inside the verdict you were writing anyway, is
  enough to drive both the policy gate and venue memory. The run below
  never sets the top-level key at all.

A minimal spec, enough to drive a run, invented for this page rather than
quoting any real paper:

```toml
questions = ["What does the paper study?"]

[verdict]
recommend = "minor revision"
venue = "PRX"
major_minor = "minor"
```

The repository ships a full annotated example,
[`review-spec.example.toml`](../review-spec.example.toml), with
`[section_lengths]` and `[editor_answers]` filled in and a comment on
every key — copy it next to a session and edit it, rather than writing a
spec from nothing.

## Why TOML

TOML rather than JSON or YAML, for two reasons that are both about the
verdict rather than the mechanics of parsing. `tomllib` has been in the
Python standard library since 3.11, so reading a spec adds no dependency.
And TOML has triple-quoted multi-line strings, so a verdict running to a
thousand words — the length a considered recommendation actually runs to
— stays readable and wrapped like text in the file. JSON would force that
same verdict onto one line with every quote and newline escaped; YAML
would read it fine but is a dependency the package does not otherwise
need (`refereekit/spec.py:8-11`).

## Parsed first

`review` loads `--spec` before it builds a backend and before it opens the
PDF — ahead of even the venue gate (`refereekit/cli.py:207-210`). A spec
that cannot drive a run therefore fails before anything is sent anywhere,
and before the session directory exists at all.

All three ways a spec is rejected are reproducible offline — no backend
and no manuscript needed, since only `refereekit/spec.py` reads the file.

**No questions.** An empty `questions` array:

```bash
printf 'questions = []\n' > work/bad.toml
refereekit review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/bad.toml
```

```text
review failed: work/bad.toml: 'questions' is empty; a review that asks nothing leaves an empty claim pool and the draft would have nothing verified to cite
```

**No verdict table.** A spec with questions but no `[verdict]` at all:

```bash
printf 'questions = ["q"]\n' > work/bad.toml
refereekit review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/bad.toml
```

```text
review failed: work/bad.toml: no 'verdict' table
```

**Missing verdict keys.** A `[verdict]` table with `recommend` but neither
`venue` nor `major_minor`:

```bash
printf 'questions = ["q"]\n[verdict]\nrecommend = "x"\n' > work/bad.toml
refereekit review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/bad.toml
```

```text
review failed: work/bad.toml: verdict is missing venue, major_minor
```

`q` above is a placeholder rather than a real question: none of these
three runs gets far enough to ask it. All three exit 2, and none leaves a
`work/spec-demo` directory behind — the failure lands before `review`
creates one. Delete the scratch file once you are done:

```bash
rm -f work/bad.toml
```

## A real spec is confidential

Unlike the example, a real spec quotes the manuscript: your questions
refer to what the paper actually says, and your verdict discusses it by
name. Write it beside the session it drives, under `work/`, never inside
the repository — the same rule as the manuscript PDF itself, and for the
same reason: `work/` is the one directory kept out of version control, so
an absent-minded `git add` cannot commit either one. See
[Confidentiality](../concepts/confidentiality.md) for what living under
`work/` buys a manuscript, and what it does not.

Keeping the spec is not only about confidentiality. It is the record of
exactly what you asked and what you concluded, and it is what makes a
review re-runnable: re-ingest the PDF after a fix and hand the same spec
to `review` again, and every question is asked exactly as before, with
nothing retyped.

## A complete offline run from a spec

This reuses [the tutorial](../tutorial.md)'s fake backend and its fixture
PDF, so you can see a spec-driven run end to end with nothing but what the
repository ships. Export the two variables from [part
1](../tutorial.md#1-set-up-the-fake-backend) if they are not already set,
then write the spec next to the session it will drive:

```bash
mkdir -p work/spec-demo
cat > work/spec-demo/review.toml <<'EOF'
questions = ["What does the paper study?"]

[verdict]
recommend = "minor revision"
venue = "PRX"
major_minor = "minor"
EOF
```

Then run it:

```bash
refereekit review tests/fixtures/real_paper.pdf --session work/spec-demo --spec work/spec-demo/review.toml
```

```text
SUMMARY:
On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".
On p. 1 the paper says "a finite set of nodes". Page 2 sets up the model. On p. 3 it says "words that are not on that page".  ⚠ CITATION FAILED: page (3); unquoted, not verified: page (2)
review complete: work/spec-demo/ours/report.txt, work/spec-demo/ours/editor.txt (2 flag(s))
```

Compare this with [the tutorial's piped
run](../tutorial.md#2-run-the-review): the summary, the one question asked
and its checked answer, and the final count are identical, because it is
the same fixed backend answering the same one question. What is missing
is every prompt: no `question>`, no `verdict (recommend)>`, not even
squashed onto one line the way the tutorial's own piped block runs them
together. `scripted_input` builds an `input_fn` that receives each prompt
string and ignores it (`refereekit/spec.py:84-85`); the piped tutorial run
still shows every prompt because that run falls back to Python's own
`input()`, which prints its prompt before reading, piped or not
(`refereekit/agent/loop.py:20`).

Nothing above sets a top-level `venue`, only `[verdict].venue` — and the
run still opened `work/spec-demo/memory.db` and ran the policy gate
against `PRX`, exactly as a top-level key would have: the fallback from
[Spec format](#spec-format) working as documented.

Delete `work/spec-demo` once you are done experimenting, the same as any
other scratch session.

## See also

- [Reviewing for a journal](journal-review.md) — the same `review`
  command, answered by typing at each gate instead of from a spec.
- [Command reference](../reference/cli.md) — every flag `review` accepts,
  including `--spec`.
- [`review-spec.example.toml`](../review-spec.example.toml) — the full
  annotated example, with every optional table filled in.
