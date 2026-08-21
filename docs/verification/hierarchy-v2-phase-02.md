# Hierarchy V2 Phase 02 — Candidate Contract

Status: **PASS**

`RetrievedCandidate` now separates immutable IR rank from context consumption order with `retrieval_final_rank` and `context_candidate_order`. Origin is controlled by `RETRIEVAL` / `HIERARCHY_CHILD`; V2 permits only `DIRECT_CHILD` at depth 1.

Base candidates retain their original branch scores/ranks, fusion score, and RRF rank. Hierarchy children have null dense, lexical, fusion, and RRF diagnostics and carry authoritative child `legal_unit_id`, primary anchor fields, and deterministically sorted anchor references.

The public `/retrieve` response temporarily retains `final_rank` as an explicit compatibility alias: it equals `retrieval_final_rank` for IR candidates and is null for hierarchy children. Block 5 no longer relies on that alias. Contract and API tests pass.

