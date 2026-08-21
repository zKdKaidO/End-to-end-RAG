# Hierarchy V2 Phases 03–20 — Production Implementation

Status: **PASS**

- Placement: after immutable RRF Top 10 and one base bulk hydration; before Block 5.
- Relation: stored `chunks.legal_unit_id → legal_units.parent_unit_id → child chunks` only.
- Depth: exactly one; the SQL is non-recursive and does not select parents, siblings, adjacent units, or same-article members.
- Bounds: 10 anchors, 4 emitted children per anchor, 20 added globally, 30 combined maximum.
- Lookup: one parameterized SQL statement over `chunks` and `legal_units`; no N+1 and no new table.
- Ordering: anchor RRF rank, then child unit `char_start`, child unit UUID, child `chunk_index`, child UUID.
- Filtering: request document filter is bound inside SQL and checked defensively before emission.
- Dedup: chunk UUID identity; base candidate wins; multiple structural discoveries emit once with stable primary/all anchor references.
- Fallback: hierarchy failure is atomic and returns the already hydrated base anchors with `BASELINE_FALLBACK` diagnostics.
- Block 5: consumes `context_candidate_order`, preserves exact dedup, source numbering, token accounting, whole chunks, Greedy Stop, 4,096-token budget, and real child provenance.
- Block 6: unchanged; source IDs continue mapping to authoritative child chunk/document provenance.

Representative real case `v2_social_scope` returned 10 immutable anchors plus three direct children; the three children were precisely the expected evidence chunks and exposed no fabricated IR scores.

