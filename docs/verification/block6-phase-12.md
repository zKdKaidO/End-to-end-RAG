# Block 6 Phase 12 — Disconnect, timeout, and stream failure

The guarded stream races provider progress with disconnect checks. Disconnect cancels the pending provider read, closes the upstream async generator/HTTP context, logs `CLIENT_DISCONNECTED`, and emits no `done`. A deterministic cancellation test verifies the upstream `finally` cleanup executes.

Typed provider-unavailable and timeout paths map to 503/504 before non-stream output; stream failures map to a safe SSE `error`. Tests verify failure after deltas has no following `done`. Automatic generation retry is not implemented, so no answer splicing is possible.

Result: PASS.
