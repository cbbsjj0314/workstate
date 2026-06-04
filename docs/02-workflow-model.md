# Workflow Model

WorkState models repo-level workflow state across N repositories.

The current dogfooding workflow is:

- ChatGPT acts as the master planning/control session.
- Codex acts as a delegated implementation or planning worker.
- The user decides next actions, creates tickets, delegates work, reviews plans
  or PRs, checks CI, requests revisions, and merges.
- The workflow is spec-driven, PR-native, and CI-gated when a repository uses
  that workflow.

The core model remains tool-agnostic. It must also support local-only work,
pre-PR work, plan-only AI output, non-GitHub workflows, and future non-Codex AI
agent workflows.

## Actors

- `user`: the human operator deciding and approving work.
- `planning_session`: the ChatGPT master/control session today; a generic
  planning actor/session in future workflow profiles.
- `ai_agent`: Codex today, or another delegated AI agent later.
- `ci`: automated checks when a workflow uses CI.
- `reviewer`: a human or process responsible for review.
- `external_system`: any non-core system that may provide a signal.

## Core State

Each repository checkpoint records:

- repository identity
- current work item
- `phase`: the current state of the work item
- `waiting_actor`: who must act next
- `next_action`: the concrete resume action
- last checkpoint time
- short notes or planning context

`phase` and `waiting_actor` must not be collapsed. A repo can be in
`agent_plan_ready` while waiting on `user`, or in `ci_pending` while waiting on
`ci`.

## Optional Signals

External signals may include PR URL, CI result, review state, Git branch, dirty
state, or external status. These signals can explain the current phase, but the
core checkpoint must still be useful without them.
