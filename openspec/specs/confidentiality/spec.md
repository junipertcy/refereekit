# confidentiality Specification

## Purpose

Keep a manuscript under review confidential. This is the design's centre rather
than a feature of it: manuscript text reaches a model only where the referee has
said it may, never enters a persistent store, and never enters the repository.

Controls in this capability fail closed. Where a control cannot verify something,
it refuses rather than proceeds.

Only behaviour that a change has specified appears below. The leak guard, the
retention attestation and the repository ignore rules are implemented and covered
by tests, but have not yet been through a change, so they are not written down
here.

## Requirements

### Requirement: Every manuscript-sending command honours venue policy

Every command that can send manuscript-derived text to a model SHALL refuse,
before a backend is constructed and before the manuscript is read, when the
venue recorded for the session prohibits sending submissions to outside models.

This SHALL hold as a property of the command surface rather than a list
maintained by hand. A command added later that sends manuscript-derived text
SHALL inherit the refusal, and the suite SHALL fail if one does not.

"Manuscript-derived" includes author responses. A response quotes and
characterises the paper, which is why `or-responses` sends with
`manuscript_ok=True` — and why it shipped ungated while four sibling commands
were gated.

The venue SHALL be taken from the session's recorded state when it is not given
on the command line. A session created by `or-fetch` already records its venue,
so a command run against that session honours the prohibition without the
referee restating it.

#### Scenario: A prohibited venue stops a drafting command
- **GIVEN** a session whose recorded venue prohibits outside models
- **WHEN** any command that would send manuscript-derived text is run
- **THEN** it exits non-zero with a message naming the venue and the prohibition
- **AND** no backend is constructed
- **AND** no output file is written

#### Scenario: The refusal survives a permissive environment
- **GIVEN** the same session
- **AND** the retention attestation is set and a transport is configured
- **WHEN** such a command is run
- **THEN** it still refuses, because venue policy is not a transport property

#### Scenario: A forgotten venue flag does not open the gate
- **GIVEN** a session fetched from a prohibiting venue, so its venue is recorded
- **WHEN** a review is run against it without naming the venue on the command line
- **THEN** it refuses, using the venue recorded in the session

#### Scenario: A new manuscript-sending command cannot ship ungated
- **GIVEN** a command is added that reaches a model with manuscript-derived text
- **WHEN** the suite runs
- **THEN** it fails unless that command refuses for a prohibited venue
- **AND** the check discovers commands from the command surface rather than from
  a hard-coded list

#### Scenario: An unlisted venue is unaffected
- **GIVEN** a session whose venue is not listed as prohibiting outside models
- **WHEN** such a command is run
- **THEN** it proceeds, because the policy is an explicit denial and not an allow-list

#### Scenario: Read-only commands are not gated
- **GIVEN** a session whose venue prohibits outside models
- **WHEN** a command that sends nothing to a model is run, such as fetching or
  verifying an anchor locally
- **THEN** it proceeds normally
