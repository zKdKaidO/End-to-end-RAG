# Legal Hierarchy Retrieval V2 — Architecture Design

Status: **IMPLEMENTED — BLOCK 4 RE-FROZEN WITH LEGAL HIERARCHY RETRIEVAL V2**

## Scope and measured basis

This design narrowly amends the Block 4/5 boundary with one-hop, bounded, direct-child legal-structure enrichment. It does not alter query embedding, Dense Top 50, Lexical Top 50, RRF, RRF k, base Top 10, document filtering, Block 5 budgeting, Block 6, generation prompts, or public request controls.

The frozen V2 experiment measured the following for direct-child replay:

| Metric | Baseline | H2 direct children |
|---|---:|---:|
| Multi-evidence complete retrieval | 33.33% | 66.67% |
| Required-evidence recall | 46.67% | 81.11% |
| Hit@10 | 85.45% | 92.73% |
| Hit@1 | 63.64% | 63.64% |
| MRR | 0.7087 | 0.7217 |
| Average candidates | 10.00 | 13.36 |
| Average context tokens | 2,096.2 | 2,416.7 |
| Budget-exhausted cases | 0/55 | 11/55 |
| Retrieved expected evidence dropped | 0 | 0 |

Broader parent, sibling, article, and adjacency expansion added noise and caused context regressions. V2 therefore supports direct children only.

## Placement decision

| Option | Strengths | Risks | Decision |
|---|---|---|---|
| A. RRF Top 10 → Block 4 hierarchy enrichment → Block 4 output | One retrieval contract; `/retrieve`, answer orchestration, evaluation, and debug observe the same candidates; natural ownership of data lookup and hydration | Amends Block 4 output and requires a small Block 5 compatibility change later | **Selected** |
| B. Frozen Block 4 output → separate component → Block 5 | Keeps current Block 4 DTO untouched | `/retrieve` and answer retrieval differ; orchestration owns database enrichment; debug/evaluation can drift | Rejected |
| C. Expansion before final Top K/RRF completion | Children could compete earlier | Requires fabricated or incomparable scores and changes RRF semantics | Rejected |

The selected placement is an internal `LegalHierarchyExpander` substage of Block 4 after the canonical base Top 10 have been ranked and hydrated. It is structurally separate from retrieval ranking:

1. Dense and lexical branches produce their frozen pools.
2. Python RRF produces and freezes the base Top 10 anchors.
3. One bulk hydration obtains the canonical base anchor chunks.
4. `LegalHierarchyExpander` performs one bounded bulk direct-child lookup.
5. Application code deduplicates and deterministically orders the combined stream.
6. The enriched candidate stream crosses the Block 4/5 boundary.

This placement allows a safe baseline fallback because base anchors are already hydrated if optional hierarchy enrichment fails.

## Anchor contract

- Anchor source: canonical production RRF Top 10 only.
- Anchor order: ascending immutable RRF `final_rank` (1–10), then `chunk_id` only as an invariant tie-break.
- Maximum anchor candidates: 10.
- Duplicate anchor legal units: collapse to the earliest RRF anchor for lookup; preserve all contributing anchor chunk IDs diagnostically.
- Anchors without `legal_unit_id`: valid baseline candidates but not expandable.
- Public API ownership: all limits are server-owned and absent from `AnswerRequest` and `RetrievalRequest`.

## Authoritative direct-child relation

The only V2 relationship is:

```text
anchor chunk
  → chunks.legal_unit_id
  → legal_units.id (anchor unit)
  → legal_units.parent_unit_id = anchor unit id (direct child unit)
  → chunks.legal_unit_id = direct child unit id (child chunks)
```

Constraints:

- `hierarchy_depth` is exactly 1.
- No recursive descendants, siblings, parents, same-article expansion, page adjacency, text inference, article-number guessing, or LLM classification.
- Child and anchor documents must match.
- When a request has `document_ids`, the allowed-document predicate is applied in the hierarchy SQL and checked again in memory.

## Expansion bounds

Proposed initial server-owned configuration for the future implementation:

| Setting | Value | Rationale |
|---|---:|---|
| `HIERARCHY_ENABLED` | `true` after explicit rollout approval | Feature is not enabled by this design task |
| `HIERARCHY_MAX_ANCHORS` | 10 | Exactly the frozen base Top 10 |
| `HIERARCHY_MAX_CHILDREN_PER_ANCHOR` | 4 | Matches the successful experiment bound |
| `HIERARCHY_MAX_CANDIDATES_ADDED` | 20 | Frozen replay added at most 17; 20 preserves parity with a small guard margin |
| `HIERARCHY_DEPTH` | 1 | One-hop contract |

The global output maximum is therefore 30 candidates: 10 base anchors plus at most 20 hierarchy children. These are hard caps, not tuning hints. Per-anchor child selection uses source order before the global cap.

## Bulk database lookup

The implemented repository method accepts ordered anchor chunk IDs and the already validated document filter. It performs one parameterized query conceptually equivalent to:

```sql
WITH anchors AS (
    SELECT c.id AS anchor_chunk_id, c.document_id, c.legal_unit_id
    FROM chunks c
    WHERE c.id = ANY(CAST(:anchor_chunk_ids AS uuid[]))
      AND (:document_filter_is_empty OR c.document_id = ANY(CAST(:document_ids AS uuid[])))
)
SELECT
    a.anchor_chunk_id,
    a.legal_unit_id AS anchor_legal_unit_id,
    child.id AS child_legal_unit_id,
    child.document_id,
    child.char_start,
    child.unit_type,
    child.unit_number,
    child.unit_title,
    c.id AS child_chunk_id,
    c.chunk_index,
    c.content_text,
    c.metadata_json,
    c.provenance_json
FROM anchors a
JOIN legal_units child
  ON child.parent_unit_id = a.legal_unit_id
 AND child.document_id = a.document_id
JOIN chunks c
  ON c.legal_unit_id = child.id
 AND c.document_id = a.document_id
WHERE (:document_filter_is_empty OR c.document_id = ANY(CAST(:document_ids AS uuid[])))
ORDER BY
    array_position(CAST(:anchor_chunk_ids AS uuid[]), a.anchor_chunk_id),
    child.char_start,
    child.id,
    c.chunk_index,
    c.id;
```

The exact implementation must avoid dynamic raw UUID interpolation and use bound parameters. One query returns relationship identity and hydrated child chunks; no anchor-, unit-, or child-level N+1 calls are allowed.

Tables used: `chunks`, `legal_units`. New tables: zero. No new database index is required for the initial measured corpus. The implementation audit must capture `EXPLAIN (ANALYZE, BUFFERS)` and hierarchy latency. Only if measured lookup cost becomes material should a separate schema amendment consider indexes on `legal_units(parent_unit_id, char_start, id)` and `chunks(legal_unit_id, chunk_index, id)`.

## Deterministic ordering

Selected policy: **ANCHOR → ITS DIRECT CHILDREN → NEXT ANCHOR**.

For each base anchor in RRF order:

1. emit the base anchor;
2. emit accepted direct-child chunks ordered by child unit `char_start`, child unit `id`, `chunk_index`, then child `chunk_id`;
3. continue to the next base anchor.

Why this policy:

- It exactly matches the successful H2 experiment ordering.
- It preserves each anchor before any of its structural additions.
- It keeps a child adjacent to the evidence that explains why it was added.
- It requires no synthetic score.
- The per-anchor and global caps bound the risk that one article consumes the Greedy Stop prefix.
- Frozen replay retained cross-document expected evidence under this ordering.

The ordering contract is represented by `context_candidate_order`, a new strictly increasing 1-based integer. At the amended internal boundary, the value currently named RRF `final_rank` becomes the explicit `retrieval_final_rank`; its value and semantics are preserved for base candidates and it is null for hierarchy children. It must never be repurposed as consumption order.

## Deduplication and provenance

- Authoritative expansion identity: `chunk_id`.
- Dedup happens before Block 5.
- If a child chunk already exists in the base Top 10, the base retrieval candidate wins and retains all original scores/ranks.
- If multiple anchors discover the same child, choose the primary anchor by lowest anchor RRF rank, then anchor chunk ID; record all anchor references in deterministic order for debug diagnostics.
- No fuzzy text dedup is added to retrieval. Frozen Block 5 exact normalized-content dedup remains unchanged.
- Each accepted child carries the original chunk metadata and provenance. Block 6 still maps `S_n → chunk → document → metadata → provenance` without knowing hierarchy mechanics.

## Context-pressure safety

Block 5 remains exact-token-counted Greedy Stop with whole chunks, no truncation, and the unchanged 4,096-token context budget. Retrieval V2 does not reserve or increase tokens.

Controls are limited to:

- at most 10 RRF anchors;
- duplicate anchor-unit collapse;
- at most 4 children per anchor;
- at most 20 added candidates globally;
- one hop only;
- `chunk_id` dedup before Block 5;
- stable interleaved placement.

Grouped legal-unit merging is explicitly excluded. The experiment's average 8% saving had unstable per-case effects and belongs to a future Context Strategy V2 study.

The implementation tests demonstrate that a multi-document anchor later in the RRF order remains reachable and that cap exhaustion is observable. Any retrieved-then-dropped expected evidence remains a release blocker until reviewed.

## Failure and fallback principle

Expected structural absences (`no legal_unit_id`, leaf unit, no child chunks) are `NO_EXPANSION`, not request errors. Data anomalies and cap events are observable. Because base Top 10 anchors are already hydrated, hierarchy-only lookup/hydration failures fall back to the base stream when the database session can be safely recovered. Failure before base hydration retains current Block 4 HTTP 503/500 behavior.

The full decision table is in `legal-hierarchy-retrieval-v2-failure-lane.md`.

## Observability contract

Structured logs and DebugTrace must expose distinct stages:

- `HIERARCHY_ANCHOR_SELECTION`
- `HIERARCHY_LOOKUP`
- `HIERARCHY_DEDUP`
- `HIERARCHY_ORDERING`
- `HIERARCHY_HYDRATION`

Required request-level measurements:

- `hierarchy_enabled`
- `base_anchor_count`
- `unique_anchor_unit_count`
- `anchors_expanded`
- `anchors_without_legal_unit`
- `children_examined`
- `hierarchy_candidates_added`
- `hierarchy_duplicate_count`
- `hierarchy_filter_rejection_count`
- `hierarchy_cap_reached`
- `hierarchy_lookup_ms`
- `hierarchy_total_ms`
- `hierarchy_status` (`EXPANDED`, `NO_EXPANSION`, `BASELINE_FALLBACK`)

Debug UI contract stages are Dense, Lexical, RRF Top 10, Hierarchy Expansion, Final Context Candidate Order, Block 5, and Block 6. Each child exposes origin, primary/all anchors, relationship, legal unit, document, candidate order, and later token count. The implemented Debug Cockpit displays these read-only diagnostics without tuning controls.

## Contract amendments

Block 4 unchanged:

- query embedding and model;
- Dense Top 50 and cosine search;
- Lexical Top 50 and current query semantics;
- document prefiltering;
- Python RRF and RRF k;
- base Top 10 anchor identity and RRF ranks;
- no reranker, model inference, recursion, or new table.

Block 4 amended and re-frozen:

- bounded direct-child enrichment after base ranking;
- candidate origin and hierarchy diagnostics;
- deterministic post-hierarchy `context_candidate_order`.

Block 5 requires a minimal compatibility amendment, not a redesign:

- validate/order by `context_candidate_order` rather than requiring all candidates to have an increasing non-null RRF rank;
- allow retrieval diagnostics, including fusion score and retrieval rank, to be null for hierarchy children;
- preserve all frozen dedup, S numbering, TokenCounter, whole-chunk, Greedy Stop, budget, and provenance invariants.

Block 6 impact: none. No prompt/model/provider/citation or SSE change.

## Explicit separations

- False abstention is not addressed. It belongs to Supported-Case Abstention Calibration.
- `v2_bank_board_loan_threshold` is not addressed because the correct document was absent before hierarchy expansion. Metadata-aware retrieval remains a separate experiment.
- Production hierarchy retrieval is enabled with the exact server-owned bounds above. Measured implementation evidence is recorded in `docs/verification/hierarchy-v2-final.md`.
