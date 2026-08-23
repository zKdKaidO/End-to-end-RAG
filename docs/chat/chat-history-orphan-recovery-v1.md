# Chat History V1 orphan recovery

`CHAT_TURN_STALE_AFTER_SECONDS` defaults to 600. A `STREAMING` turn uses `started_at`; a `PENDING`
turn uses `created_at`. No token heartbeat, scheduler, cron, Redis job, or new worker exists.

When a relevant session is read, its messages are read, a turn is created, or deletion is requested,
the service locks that session/active turn and rechecks both state and timestamp. Only a row still in
`PENDING`/`STREAMING` and still older than the cutoff transitions to:

- turn `FAILED`, `completed_at=now`, `failure_code=ORPHANED_STREAM_TIMEOUT`;
- safe detail `Generation was interrupted before completion.`;
- streaming assistant `FAILED`, null answer status, finalized timestamp;
- existing persisted partial content preserved (normally empty because deltas are not written).

A fresh row is left untouched. A concurrent completion cannot be overwritten because recovery uses
row locks and current-state predicates. The recovered record stays immutable; Retry creates a new
turn and client UUID.
