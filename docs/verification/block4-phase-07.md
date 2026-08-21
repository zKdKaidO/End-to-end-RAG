# Block 4 Phase 07 — Retrieval API

Status: PASS

Canonical endpoint: `POST /retrieve`.

Frozen configurable defaults:

- dense Top-K: 50;
- lexical Top-K: 50;
- final Top-K: 10;
- RRF K: 60.

Conservative V1 rejection bounds are configured as dense 200, lexical 200, final 100, RRF K 10,000, and 100 document IDs. Values are rejected rather than clamped.

Tests cover defaults, custom values, deduplicated UUID filters, empty/whitespace queries, invalid and excessive Top-K, invalid UUIDs, over-limit model input, zero results, dependency errors, internal errors, and the exact response fields. Input fields `offset`, `page`, and `cursor` are rejected. `request_id` is not accepted in the body; the existing middleware context is propagated instead.

Failure mapping:

- validation and query length: HTTP 400;
- PostgreSQL/model unavailable: HTTP 503;
- unexpected retrieval failure: HTTP 500;
- no candidates: HTTP 200 with `{"results": []}`.
