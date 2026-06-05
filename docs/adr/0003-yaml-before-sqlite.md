# ADR 0003: YAML/JSON Before SQLite

## Status

Accepted as an early inspectability preference. The final persisted schema and
storage format must still be validated during M0 and M1.

## Decision

WorkState may use YAML/JSON for early examples, spikes, or local-first
inspection before introducing SQLite or another storage approach.

## Rationale

The product contract is still being validated. Human-readable examples keep the
model easy to inspect, edit, diff, and review while WorkState tests automatic
event capture, repository snapshots, derived workflow state, and repair flows.

## Consequences

- Conceptual examples can remain transparent and local-first.
- YAML/JSON examples do not define the final persisted schema.
- SQLite or another storage approach can be introduced later if M0/M1 validation
  justifies it.
