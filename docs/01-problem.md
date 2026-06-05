# Problem

WorkState helps a user recover repo-specific workflow state after stepping away
from active work.

The core resume question is:

> What is waiting for whom?

The answer should be derived from observable evidence, not repeatedly typed into
a note.

## Real Competitors

WorkState competes with:

- maintaining a plain note
- rereading ChatGPT history
- reopening Codex sessions
- inspecting multiple GitHub tabs
- remembering work mentally

WorkState fails if it requires more effort than those alternatives.

## What The User Needs To Recover

After a break, the user needs to know:

- what happened recently
- what changed in the local working tree
- whether work was committed or pushed
- whether a PR exists or was merged
- whether validation or CI is pending, passed, failed, or not observed
- whether an AI agent is still active
- which actor last worked
- whose attention is likely needed
- which interpretations still need confirmation
- what action is suggested next, if any

WorkState should preserve the distinction between objective facts and workflow
interpretations. A wrong interpretation should not corrupt the observed history
that supported it.

## Product Bar

WorkState must be more convenient than a plain note. It should not require the
user to run a manual checkpoint after every workflow transition, repeatedly tell
ChatGPT to record state, or manually reproduce data already available from
integrations.
