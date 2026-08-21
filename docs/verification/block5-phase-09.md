# Block 5 Phase 09 — Edge cases

Status: PASS

Verified cases:

- empty retrieved list returns an empty valid package with `NONE`;
- missing or whitespace-only `content_text` is rejected;
- malformed candidate and UUID values are rejected;
- zero, negative, boolean, and non-integer budgets are rejected;
- duplicate-only inputs retain one highest-ranked candidate with documented counts;
- exact-size budget accepts the whole candidate;
- one-token-smaller budget rejects the whole candidate;
- first evidence larger than budget returns `TOP_EVIDENCE_EXCEEDS_CONTEXT_BUDGET` and empty context;
- missing legal metadata is handled without fabrication;
- TokenCounter failure becomes a typed `TOKEN_COUNTING` dependency error;
- non-additive deterministic token counts still produce an exact final recount.
