# WorkState

WorkState is a local-first CLI contract for tracking workflow state across
multiple personal repositories.

The central question is:

> What is waiting for whom?

WorkState is not primarily about recent commits, file changes, or coding time.
It is about recovering repo-specific workflow state after stepping away for
hours, sleeping, or going to work.

## Product Definition

WorkState tracks the current work item for each repository, where that work is
in the workflow, who must act next, and the next action needed to resume.

It is designed for N repositories. The current dogfooding setup may use around
three repositories, but the product model must not be hard-coded to three.

## Core Model

Core workflow state:

- repository identity
- current work item
- current phase
- waiting actor / next actor
- next action
- last checkpoint
- short notes or planning context

`phase` and `waiting actor / next actor` are distinct. `phase` describes the
current state of the work item. `waiting actor / next actor` describes who must
act next.

Optional external signals:

- GitHub PR
- CI status
- review status
- Git branch or dirty state
- external system status

PR, CI, GitHub, review, and Git state are useful signals or gates in some
workflows. They are not mandatory core workflow state.

## MVP Direction

- Local-first CLI
- Manual checkpoint first
- Multi-repo resume view
- YAML/JSON storage first
- Optional Git/GitHub adapter later
- No automatic ChatGPT/Codex scraping in the MVP

## Docs

- [Problem](docs/01-problem.md)
- [Workflow model](docs/02-workflow-model.md)
- [State machine](docs/03-state-machine.md)
- [CLI contract](docs/04-cli-contract.md)
- [MVP scope](docs/05-mvp-scope.md)
- [ADRs](docs/adr)
