# ADR 0004: Automatic Event Capture As Core Requirement

## Status

Accepted

## Decision

Automatic workflow event capture is a core WorkState product requirement where
integrations permit.

Manual checkpointing remains available as fallback and repair, but it is not the
intended primary UX.

## Rationale

Manual checkpointing alone does not provide enough product value. If the user
must repeatedly record `phase`, `waiting_for`, and `next_action`, WorkState is
not meaningfully better than a plain note.

WorkState should capture objective events from ChatGPT, Codex, Git, GitHub, CI,
and related tools where integrations permit. Those integrations may be partial
and adapter-specific, so the event model must remain tool-agnostic.

Uncertain interpretation must not overwrite objective facts. Correcting an
interpretation records corrective information or an override while preserving
the observed evidence that led to the interpretation.

## Consequences

- The resume view becomes the primary product experience.
- `likely_waiting_for` is derived from evidence and confidence, not manually
  asserted as source-of-truth data.
- M0 must validate integration feasibility before final implementation details
  are locked.
- Manual checkpointing is still necessary for local-only workflows, failed
  capture, and repair.
