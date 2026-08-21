# Block 5 Phase 11 — Observability

Status: PASS

Structured completion diagnostics include:

- request ID;
- candidate, duplicate, selected, and dropped counts;
- context budget and exact token count;
- budget utilization;
- budget exhausted flag and controlled stop reason;
- context build milliseconds;
- optional tokenizer provider and tokenizer ID.

A recording-logger test verifies the diagnostic keys and asserts that a sensitive legal-content marker and the assembled `context_text` are absent from log events. Block 5 does not handle or log vectors, and it does not log provenance JSON.
