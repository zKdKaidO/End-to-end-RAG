# Block 6 Phase 08 — POST /answer

`POST /answer` accepts only `query_text` and optional UUID `document_ids`, propagates middleware request ID, and returns the exact generation contract.

Verified valid query, canonical document filter, empty/whitespace query, invalid UUID before retrieval, no evidence, prompt overflow, typed 503/504 provider failures, real generation, and forbidden client profile fields. Live canonical response: HTTP 200, `COMPLETED`, citation validation `PASS`, one mapped citation.

Result: PASS.
