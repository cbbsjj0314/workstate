# ADR 0001: Local-First Manual Checkpoint

## Status

Accepted

## Decision

WorkState starts as a local-first tool with manual checkpointing.

## Rationale

The first product problem is workflow recovery, not automation coverage. Manual
checkpointing lets the user record the current work item, phase, waiting actor,
next action, and planning context without depending on GitHub, CI, Git, or AI
agent scraping.

## Consequences

- WorkState can support local-only repositories from the start.
- Checkpoints may be incomplete if the user does not update them.
- External adapters can be added later without changing the core model.
