# State Machine

WorkState represents the current phase of each repository's work item. A
repository does not need to pass through every phase.

## Core Phases

- `needs_ticket`: the next work item has not been defined.
- `needs_prompt`: an AI agent prompt is needed but not prepared.
- `prompt_prepared`: the prompt exists but has not been sent.
- `agent_prompted`: the AI agent was instructed and work is pending.
- `agent_plan_ready`: the AI agent produced a plan awaiting review.
- `changes_applied`: the approved plan or implementation changes were applied.
- `user_review_needed`: the user must inspect a plan, changes, or result.
- `revision_needed`: the user or reviewer requested a revision.
- `done`: no next action is waiting for this work item.

## Optional PR-Native Gates

PR-native workflows may also use phases or external signals such as:

- `pr_opened`
- `ci_pending`
- `ci_failed`
- `ci_passed`
- `merge_ready`

These are optional gates, not required lifecycle states. Local-only repositories,
pre-PR work, plan-only Codex output, non-GitHub workflows, and future non-Codex
agent workflows must still be representable without them.

## Waiting Actor

`waiting_actor` is separate from `phase`.

Examples:

- `agent_plan_ready` with `waiting_actor: user`
- `agent_prompted` with `waiting_actor: ai_agent`
- `ci_pending` with `waiting_actor: ci`
- `needs_ticket` with `waiting_actor: user`

The resume view should prioritize the next actor and next action, not just the
phase name.
