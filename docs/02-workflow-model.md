# Workflow Model

WorkState models repo-level workflow recovery across N repositories.

The intended product behavior is automatic capture of observable workflow events
where integrations permit. M0 has not yet validated those integrations, so this
document describes the product contract, not current implementation capability.

## Actors And Adapters

The core model remains adapter-agnostic.

- `user`: the human operator deciding and approving work.
- `planning_session`: ChatGPT today; a generic planning actor/session in future
  workflow profiles.
- `ai_agent`: Codex today, or another delegated AI agent later.
- `ci`: automated checks when a workflow uses CI.
- `reviewer`: a human or process responsible for review.
- `external_system`: any non-core system that may provide an observable signal.

ChatGPT, Codex, Git, GitHub, and CI are important intended integrations, but
they are adapters. The core event model must not be permanently locked to those
tools.

## Model Layers

WorkState separates four layers.

1. Observed events

   Facts directly captured from integrations or local tools.

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

   Event names should describe observations, not semantic success. For example,
   prefer `file_changes_observed` over `local_changes_applied`, and keep
   `agent_reported_complete` separate from validation or work-item completion.

2. Repository snapshot

   A deterministic summary of current repository state calculated from observed
   facts and local/tool inspection. Snapshot values are not events. For example,
   `validation_not_observed` is a snapshot value, not an event.

3. Derived workflow state

   Workflow meaning inferred from events and snapshots. `likely_waiting_for` is
   derived, with provenance, evidence, confidence, and interpretation status.

4. Optional recommendation

   A suggested next action. It must be presented as a suggestion, not objective
   fact.

## Resume Experience

The resume view is the primary product experience. It should show:

- observed state
- derived workflow status
- pending interpretations
- optional suggestion

The central question remains:

> What is waiting for whom?

The answer should be supported by evidence, such as:

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
```

This evidence shape is conceptual. It distinguishes event evidence from snapshot
evidence without defining the final persisted schema.

## Proposal Behavior

Objective events should be recorded automatically when observed. Deterministic
snapshot updates should be calculated automatically. Neither should require
immediate user confirmation.

Proposals are only for uncertain interpretations. In spike mode, immediate
confirmation may be used to measure precision and recall. In product mode,
confirmation should be batched at workflow boundaries or during `resume`.

Immediate interruption should be reserved for conflicts, ambiguity that blocks
correlation, or high-risk state changes.

## Manual Repair

Manual input remains necessary when capture is missing, incomplete, or wrong.
Repair adds corrective information or overrides. It must not silently rewrite or
delete observed event history.
