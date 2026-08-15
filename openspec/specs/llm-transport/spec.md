# llm-transport Specification

## Purpose

Carry a prompt to a Claude model and return its text, and decide which
deployment of the Anthropic SDK does so.

The SDK speaks one messages API to every deployment it supports, so the
deployment is a client rather than a class. Deployments are peers: the direct
API is the default only because it is the one a referee with an API key already
has, and adding a deployment is a registry entry rather than a class.

Only behaviour that a change has specified appears below. The zero-retention
gate in `complete()` and the refusal of an unregistered deployment name are
implemented and covered by tests, but have not yet been through a change, so
they are not written down here.

## Requirements

### Requirement: Deployment defaults carry provenance

A registered deployment SHALL supply a default model id only when that id has
been exercised against that deployment. A deployment without a confirmed default
SHALL remain selectable, and SHALL refuse when no model id is supplied, naming
`REFEREEKIT_MODEL` in the refusal.

A fabricated default is worse than none. It looks authoritative, is copied into
documentation and scripts, and fails at the provider with an error that names
the model rather than the mistake.

#### Scenario: A deployment with a confirmed default needs no model id
- **GIVEN** a deployment whose default model has been run against it
- **WHEN** it is selected with `REFEREEKIT_MODEL` unset
- **THEN** the backend is built using that default

#### Scenario: A deployment without a confirmed default refuses
- **GIVEN** a deployment whose default model has never been run against it
- **WHEN** it is selected with `REFEREEKIT_MODEL` unset
- **THEN** the command refuses before contacting the provider
- **AND** the message names `REFEREEKIT_MODEL` as the setting to supply

#### Scenario: An explicit model id makes such a deployment usable
- **GIVEN** the same deployment
- **WHEN** it is selected with `REFEREEKIT_MODEL` set
- **THEN** the backend is built using the supplied id

#### Scenario: The registry states which defaults are confirmed
- **WHEN** the deployment registry is read
- **THEN** each entry distinguishes a confirmed default from the absence of one,
  so the distinction survives the next person adding a deployment
