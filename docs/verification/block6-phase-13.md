# Block 6 Phase 13 — Edge cases

Verified empty/whitespace query, invalid document UUID, zero retrieval/selection, inherited Block 5 first-evidence-too-large behavior, missing citation, unknown citation, empty provider final text, unusual `length` finish reason, long query, exact budget boundary, and one-token-over rejection.

No-evidence response is deterministic `INSUFFICIENT_EVIDENCE` with empty citations and fake-client provider-call count 0. Valid live no-document retrieval also returned HTTP 200 with this status.

Result: PASS.
