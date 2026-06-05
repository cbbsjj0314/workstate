# ADR 0001: Local-First Manual Checkpoint

## Status

Superseded by [ADR 0004](0004-automatic-event-capture-as-core-requirement.md).

## Original Decision

WorkState started as a local-first tool with manual checkpointing.

## Updated Interpretation

Manual checkpointing remains useful as fallback and repair, but it is not the
intended primary UX.

The current product contract requires automatic workflow event capture where
integrations permit. Manual input should add missing context, corrective
information, or overrides when capture is unavailable, incomplete, ambiguous, or
wrong.

## Consequences

- Local-first recovery remains a core requirement.
- Manual checkpoints are no longer the MVP's primary workflow.
- Observed event history, repository snapshots, derived workflow state, and
  batched interpretation confirmation define the current product direction.
