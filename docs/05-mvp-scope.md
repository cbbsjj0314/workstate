# MVP Scope

WorkState's MVP direction is automatic workflow recovery where integrations
permit, with manual repair always available.

The current repository contains only the product contract. It does not yet
implement the integrations or runtime CLI.

## M0: Integration Feasibility Spikes

M0 verifies whether the intended capture model is practical.

M0 should test:

- ChatGPT MCP tool invocation reliability
- Codex lifecycle event capture
- handoff correlation
- file-change and turn-completion observation
- Git and GitHub state collection
- confirmation frequency and UX friction

Preferred spike order:

1. Codex hooks
2. ChatGPT MCP
3. local Git and `gh` polling integration

M0 experiments may use immediate per-transition confirmation to measure
precision and recall. That is not the intended final UX.

## M1: Dogfooding MVP

M1 should be usable across multiple repositories.

M1 includes at least:

- validated local storage approach for observed event history
- repository snapshot
- derived workflow state
- multi-repository resume view
- partial ChatGPT event capture
- Codex lifecycle capture
- local Git inspection
- GitHub/CI polling
- manual repair/fallback
- batched interpretation confirmation

M1 should not require the user to repeatedly enter `phase`, `waiting_for`, or
`next_action` as normal workflow maintenance.

## Deferred

Deferred until after M0/M1 validation:

- final persisted schema
- event replay infrastructure
- compaction
- event migrations
- distributed consistency
- production-grade event-sourcing abstractions
- final wire protocol for handoff metadata
- broad provider marketplace or market analysis

The current goal is logical event-history preservation plus snapshot
materialization, not a full event-sourcing framework or a locked persistence
format.

## Success Criteria

WorkState succeeds when:

- most objective events are captured automatically where integrations permit
- the user does not repeatedly enter `phase`, `waiting_for`, or `next_action`
- repository state can be recovered quickly after stepping away
- confirmation is infrequent and batched
- incorrect interpretation does not corrupt objective history
- the resume view is more useful than rereading ChatGPT/Codex sessions or
  maintaining a plain note
- N repositories are supported without hard-coding the current dogfooding count

## Failure Criteria

WorkState fails when:

- the user must run a manual checkpoint after every workflow transition
- the user must repeatedly tell ChatGPT to record state
- confirmation is more burdensome than writing a note
- WorkState frequently records incorrect semantic state
- event history is collected but does not help the user resume work
- automatic capture requires the user to manually reproduce data already
  available in integrations
