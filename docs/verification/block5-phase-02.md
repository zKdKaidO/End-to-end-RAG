# Block 5 Phase 02 — Schemas and TokenCounter contract

Status: PASS

Implemented a production `TokenCounter` Protocol with only:

- optional `provider`;
- optional `tokenizer_id`;
- `count(text) -> int`.

No provider, generation model, proxy tokenizer, model weights, or production fake counter was added. Deterministic counters exist only under `tests/context_doubles.py`.

Implemented strict `ContextPackage`, `SelectedEvidence`, and controlled `StopReason` schemas. Validation tests cover required dependency injection, invalid budgets, invalid candidate shapes, empty candidates, UUIDs, rank ordering, and arbitrary stop-reason rejection.

The context budget remains a required internal service argument. It is not exposed through an API or client schema.
