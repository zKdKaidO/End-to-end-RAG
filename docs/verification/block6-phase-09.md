# Block 6 Phase 09 — Citation parser and validator

Deterministic regex parser accepts authoritative `[S1]` / `[S15]` syntax, handles adjacency and repetition, preserves first-seen order, and ignores malformed forms. Tests cover no citation, unknown IDs, all-valid, mixed valid/invalid, and missing citations.

- Unknown reference: `COMPLETED_WITH_WARNINGS` / `INVALID_REFERENCES`.
- Non-empty answer with no valid citation: `COMPLETED_WITH_WARNINGS` / `MISSING_CITATIONS` (ungrounded-answer warning).
- Invalid IDs receive no citation object or provenance.
- No regeneration/retry occurs.

Result: PASS.
