# Event And Snapshot Model

This document is the canonical conceptual data-model contract for WorkState.

It does not define a final production schema, enum set, migration format,
event-store implementation, immutability mechanism, replay architecture, or
persistence format. Those details must be validated during M0 and M1.

## Layers

WorkState separates:

- observed events
- repository snapshots
- derived workflow state
- optional recommendations

Facts and interpretations are separate layers.

## Observed Events

An observed event is a fact directly captured from an integration or local tool.

Examples:

- `planning_prompt_created`
- `agent_prompt_submitted`
- `agent_turn_completed`
- `plan_output_observed`
- `file_changes_observed`
- `commit_created`
- `branch_pushed`
- `pr_created`
- `pr_merged`
- `validation_started`
- `validation_passed`
- `validation_failed`
- `ci_pending`
- `ci_passed`
- `ci_failed`
- `agent_reported_complete`

Use objective names. Avoid names that imply semantic success when only an
observation occurred.

Naming rules:

- prefer `file_changes_observed` over `local_changes_applied`
- prefer `plan_output_observed` unless an integration provides an authoritative
  plan-completed event
- keep `agent_reported_complete` separate from validation success or work-item
  completion

## Repository Snapshot

A repository snapshot is a deterministic summary of current repository state.

Conceptual example:

```yaml
working_tree:
  has_changes: true
  changed_file_count: 4

commit:
  latest_commit: null

remote:
  pushed: false

pull_request:
  exists: false

validation:
  status: not_observed

execution:
  active_actor: none
  last_actor: codex
  last_event: agent_turn_completed
```

`validation_not_observed` is a snapshot value, not an event.

## Derived Workflow State

Derived workflow state is workflow meaning calculated from observed events and
snapshots.

Conceptual example:

```yaml
derived_workflow:
  likely_waiting_for: user
  confidence: high
  evidence:
    - kind: event
      ref: agent_turn_completed
    - kind: event
      ref: file_changes_observed
    - kind: snapshot
      ref: validation.status
      value: not_observed
  provenance:
    source: rule
  interpretation_status: inferred
```

`likely_waiting_for` remains an important product concept, but it is derived. It
must not be treated as an objective source-of-truth field.

The evidence shape above is conceptual. It distinguishes event evidence from
snapshot evidence without defining the final persisted schema.

Derived state must expose:

- provenance
- evidence
- confidence or certainty
- interpretation status

## Provenance And Interpretation Status

Use these terms precisely:

- `observed`: an event directly captured from an integration or local tool
- `inferred`: a workflow interpretation derived from evidence
- `confirmed`: an inferred interpretation accepted by the user
- `overridden`: an inferred or previously confirmed interpretation corrected by
  the user

Observed facts do not transition into `confirmed` or `overridden`.
Interpretations can be inferred, confirmed, or overridden. Correcting an
interpretation records corrective information additively and does not erase the
supporting observed events.

## Proposal Behavior

Proposals are only for uncertain interpretations.

- Objective events should be recorded automatically when observed.
- Deterministic snapshot updates should be calculated automatically.
- Uncertain semantic interpretations create proposals.
- Product-mode confirmation is batched at workflow boundaries or during
  `resume`.
- Spike-mode immediate confirmation may be used to measure precision and recall.

Unconfirmed proposals must be visible during `resume`.

## Optional Recommendation

WorkState may suggest a next action, but must not present it as objective fact.

Conceptual example:

```yaml
recommendation:
  action: review_diff
  source: rule
  confidence: medium
```

WorkState does not replace the user, reviewer, or coding agent in deciding
whether a plan is good, changes satisfy the requirement, code quality is
acceptable, more revisions are needed, a PR should be merged, or a work item is
truly complete.

## Handoff Correlation

A stable handoff ID can correlate related events across tools:

```text
WorkState-Handoff-ID: ws_01J...
```

Its purpose is to connect observations such as:

```text
ChatGPT: revision prompt created
Codex: revision prompt received
```

The visible header is acceptable for an M0 spike. The final UX should pass this
metadata automatically where possible. The user should not manually manage
handoff IDs.

A random stable ID is preferred over relying only on content hashes. Raw prompt
content should not be required for correlation.

This document does not define the final wire protocol.

## Privacy Defaults

Default persisted data should be limited to:

- event type
- repository identity
- source session or turn ID
- timestamp
- stable correlation ID
- content hash or local HMAC where useful
- short redacted summary

Raw ChatGPT or Codex prompt content should be opt-in. WorkState should not store
credentials, secrets, or full source code by default.
