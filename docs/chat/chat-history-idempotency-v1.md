# Chat History V1 idempotency and concurrency

The client creates a UUID before a new logical submission. The request hash is SHA-256 over canonical
JSON containing version 1, the trimmed query, and sorted/deduplicated document UUID scope. It excludes
request time, network metadata, and trace ID.

| Existing `(session_id, client_turn_id)` | Hash | Result |
|---|---|---|
| none | — | create the turn |
| `COMPLETED` | same | replay persisted `start`, one full `delta`, `done`; `replayed=true`; no provider call |
| fresh `PENDING/STREAMING` | same | `409 TURN_IN_PROGRESS` with IDs/state |
| stale active | same | reconcile to `FAILED`; return terminal conflict; explicit Retry needs a new ID |
| `FAILED` | same | `409 TURN_FAILED`; no rerun |
| `CANCELLED` | same | `409 TURN_CANCELLED`; no rerun |
| any | different | `409 IDEMPOTENCY_KEY_CONFLICT` |

Session row locking provides deterministic sequence allocation and good error UX. The database unique
constraint remains authoritative for same-key races. The partial unique index remains authoritative
for different-key active-turn races. Constraint names are inspected precisely after `IntegrityError`;
unrelated integrity errors are not relabelled.

A replay reuses the stored message and snapshots. It never inserts another turn/snapshot and never
simulates provider-token timing.
