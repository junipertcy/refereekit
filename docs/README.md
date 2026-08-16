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
