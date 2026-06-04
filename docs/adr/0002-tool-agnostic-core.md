# ADR 0002: Tool-Agnostic Core

## Status

Accepted

## Decision

WorkState keeps the core workflow model tool-agnostic.

## Rationale

ChatGPT is the planning session today, and Codex is the delegated AI agent
today. Those are workflow profiles, not permanent requirements. The core model
must also support non-Codex agents, non-GitHub workflows, local-only work, and
manual planning.

## Consequences

- Core state uses generic actors such as `planning_session` and `ai_agent`.
- ChatGPT, Codex, GitHub, PR, CI, review, and Git details are optional context
  or external signals.
- Future workflow profiles can map their tools onto the same core fields.
