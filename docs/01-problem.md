# Problem

WorkState helps a user recover repo-specific workflow state after stepping away
from active work.

The core problem is not tracking:

- recent commits
- file changes
- coding time

The core problem is answering:

> What is waiting for whom?

After a break, the user needs to recover:

- what was being discussed in the planning session
- whether a ticket exists
- whether an AI agent prompt is needed or already prepared
- whether the agent was instructed
- whether the agent only produced a plan
- whether the plan was applied
- whether a PR exists, if the workflow uses PRs
- whether the next action is review, CI handling, revision, merge, or a new
  ticket

WorkState should make that state visible across N repositories without requiring
every repository to use GitHub, CI, PRs, or the same AI agent.
