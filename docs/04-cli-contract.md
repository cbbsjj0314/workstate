# CLI Contract

This document defines intended commands only. It does not define or implement a
runtime CLI.

## `workstate checkpoint`

Record or update the checkpoint for one repository.

Intended inputs:

- repository identity
- current work item
- phase
- waiting actor / next actor
- next action
- notes or planning context
- optional external signals

## `workstate resume`

Show the multi-repo resume view.

The view should answer:

> What is waiting for whom?

It should work across N repositories and should not require GitHub, CI, PR, or
Git state.

## `workstate status`

Show the current checkpoint for one repository or all repositories.

## `workstate next`

Show the next action the user should consider, based on waiting actor, next
action, and checkpoint time.

## `workstate repos`

List repositories known to WorkState.

The dogfooding setup may include around three repositories, but the command
contract must support N repositories.
