# ADR 0003: YAML/JSON Before SQLite

## Status

Accepted

## Decision

WorkState starts with YAML/JSON storage before SQLite.

## Rationale

The MVP needs a small, inspectable checkpoint format. YAML/JSON keeps early
state easy to read, edit, diff, and review while the product contract is still
being validated.

## Consequences

- Early checkpoints remain transparent and local-first.
- Advanced querying is deferred.
- SQLite can be introduced later if checkpoint volume or query needs justify it.
