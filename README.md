# WorkState

WorkState is a local-first workflow recovery tool for personal repositories.

It is designed to automatically capture observable workflow events where
integrations permit, calculate repository snapshots from those facts, and show
derived workflow status during resume.

The central resume question remains:

> What is waiting for whom?

That answer is derived from observed events and repository snapshots. It is not
intended to be a manually maintained source-of-truth field.

## Product Direction

WorkState should help a user recover:

- what happened recently
- what remains in the local working tree
- what has or has not been committed
- whether the branch was pushed
- whether a PR exists
- validation and CI status
- whether any execution is active
- which actor last worked
- whose attention is likely needed
- which interpretations still require confirmation

Manual checkpointing remains available as fallback or repair when automatic
capture is missing, incomplete, or wrong. It is not the intended primary UX.

## Core Model

WorkState separates four layers:

- observed events: objective facts captured from integrations or local tools
- repository snapshot: deterministic current repository state
- derived workflow state: inferred workflow meaning with evidence and confidence
- optional recommendation: suggested next action, never an objective fact

The current dogfooding setup may use around three repositories, but WorkState is
designed for N repositories. The model must not be hard-coded to ChatGPT, Codex,
GitHub, CI, PRs, or the current dogfooding count.

## Current Status

This repository currently contains a product contract. It does not implement
ChatGPT, Codex, Git, GitHub, CI, event capture, CLI runtime, or persistence
integrations yet. M0 will validate integration feasibility before the final
schema and implementation details are locked.

## Docs

- [Problem](docs/01-problem.md)
- [Workflow model](docs/02-workflow-model.md)
- [Event and snapshot model](docs/03-event-and-snapshot-model.md)
- [CLI contract](docs/04-cli-contract.md)
- [MVP scope](docs/05-mvp-scope.md)
- [Product principles](docs/06-product-principles.md)
- [ADRs](docs/adr)
