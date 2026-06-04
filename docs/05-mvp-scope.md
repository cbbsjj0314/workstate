# MVP Scope

## In Scope

- local-first CLI contract
- manual checkpointing
- multi-repo resume view
- N-repository support
- YAML/JSON storage first
- core workflow state for current work item, phase, waiting actor, next action,
  last checkpoint, and short notes
- optional external signals for PR, CI, GitHub, review, Git, or other systems

## Non-Goals

- runtime CLI implementation in this PR
- package scaffolding
- database code
- SQLite storage in the MVP
- GitHub integration code
- Git integration code
- automatic ChatGPT or Codex scraping
- hard-coding the model to ChatGPT, Codex, GitHub, PRs, CI, or three
  repositories
- generic AI productivity guidance

## MVP Rule

The MVP must be useful when the user manually records checkpoints for local
repositories. External adapters can improve accuracy later, but the core product
must not depend on them.
