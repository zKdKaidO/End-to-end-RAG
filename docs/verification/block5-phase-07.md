# Block 5 Phase 07 — Context package

Status: PASS

The final package contains the complete frozen contract: request/query, context text, selected evidence, exact count and injected budget, all four candidate counts, budget state, and controlled stop reason.

Each `S<n>` maps to exactly one selected item retaining chunk/document IDs, original content, full metadata/provenance, retrieval final rank, branch scores/ranks, fusion score, and formatted-block token count.

Count semantics:

- `candidate_count`: all candidates received from Block 4;
- `duplicate_count`: candidates removed by exact deduplication;
- `selected_count`: candidates included in context;
- `dropped_count`: `candidate_count - selected_count`.

`dropped_count` includes duplicates and candidates left after Greedy Stop; it does not imply every dropped candidate was individually evaluated.
