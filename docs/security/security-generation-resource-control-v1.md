# Generation Resource Control V1

## Reproduced weakness

The pre-hardening system limited duplicate work within one chat session but allowed one user to start provider work through multiple sessions and did not enforce a process-independent global provider limit.

## Remediation

An atomic Redis Lua admission controller now enforces:

- per-user token-bucket rate: 5/minute, burst 2;
- one active generation per user;
- one active generation globally for this single local provider;
- 240-second lease expiry for crash recovery;
- explicit release on success, provider error, preparation error, cancellation and disconnect.

Completed idempotent chat replay is resolved before admission and consumes neither a new rate token nor an inference slot. Duplicate in-progress turns retain their existing conflict behavior. Admission control occurs before Blocks 4–6/provider work; Redis failure fails closed.

## Real provider probe

One authenticated user started three sessions concurrently against real `qwen3.5:9b`. Exactly one call was admitted and completed (`start`, `done`, 24.2 s); two were rejected with `USER_GENERATION_ACTIVE` in 3.3–3.6 s. Unit/integration tests also cover global contention, rate exhaustion, all release paths, and stale lease recovery.
