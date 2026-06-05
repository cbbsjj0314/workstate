# CLI Contract

This document defines intended commands only. It does not define or implement a
runtime CLI.

The CLI should support automatic capture where integrations permit, but current
integration capability has not been implemented or validated yet.

## `workstate resume`

Show the primary multi-repo resume view.

The view should answer:

> What is waiting for whom?

The answer is derived from observed events and repository snapshots. The view
should show observed state, derived workflow status, pending interpretations,
and optional suggestions.

## `workstate status`

Show the current repository snapshot and derived workflow state for one
repository or all repositories.

## `workstate events`

Show recent observed events for one repository or all repositories.

This command should help explain why a derived interpretation exists. It should
not imply that event capture is complete before M0 validates integrations.

## `workstate inspect`

Inspect the evidence behind a derived state, pending interpretation, or
recommendation.

## `workstate confirm`

Accept or reject pending interpretations.

Confirming an interpretation does not change observed facts. Rejection or
correction records interpretation status and corrective information.

## `workstate repair`

Add corrective information, missing context, or overrides when automatic capture
is missing, incomplete, ambiguous, or wrong.

Repair must not silently rewrite or delete observed event history.

## `workstate checkpoint`

Optional manual capture fallback.

This command may record a user-supplied checkpoint when automatic capture is not
available or when a workflow needs manual repair. It is not the normal primary
workflow.
