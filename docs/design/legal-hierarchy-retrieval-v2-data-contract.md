# Legal Hierarchy Retrieval V2 — Data Contract

Status: **ACTIVE — RE-FROZEN**

## Enums

```python
from enum import Enum


class CandidateOrigin(str, Enum):
    RETRIEVAL = "RETRIEVAL"
    HIERARCHY_CHILD = "HIERARCHY_CHILD"


class HierarchyRelation(str, Enum):
    DIRECT_CHILD = "DIRECT_CHILD"
```

No other hierarchy relation is valid in V2.

## Anchor reference

```python
class HierarchyAnchorReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor_chunk_id: str                  # UUID
    anchor_legal_unit_id: str             # UUID
    anchor_retrieval_final_rank: int      # 1..10
```

References are sorted by `anchor_retrieval_final_rank`, then `anchor_chunk_id`. The first entry is the primary anchor.

## Enriched retrieval candidate

```python
class EnrichedRetrievedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Existing hydrated evidence identity/content
    chunk_id: str                         # UUID
    document_id: str                      # UUID
    content_text: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]

    # Existing retrieval diagnostics; null when not independently retrieved
    dense_score: float | None
    dense_rank: int | None
    lexical_score: float | None
    lexical_rank: int | None
    fusion_score: float | None

    # Explicit rank/order separation
    retrieval_final_rank: int | None      # RRF rank; 1..10 for RETRIEVAL, null for child
    context_candidate_order: int          # strictly increasing, 1-based total order

    # Candidate origin and authoritative legal structure
    candidate_origin: CandidateOrigin
    legal_unit_id: str | None             # UUID from chunks.legal_unit_id
    hierarchy_relation: HierarchyRelation | None
    hierarchy_depth: Literal[0, 1]
    anchor_chunk_id: str | None            # primary anchor UUID
    anchor_legal_unit_id: str | None       # primary anchor unit UUID
    anchor_retrieval_final_rank: int | None
    hierarchy_anchor_references: list[HierarchyAnchorReference]
```

`retrieval_final_rank` is the explicit boundary name for the value currently emitted as Block 4 `final_rank`. Its value and RRF semantics are preserved; it is not post-expansion order. During implementation, internal adapters must map the current base field once, then remove ambiguous reliance on `final_rank` at the Block 4/5 boundary.

## Invariants

### RETRIEVAL candidate

- `retrieval_final_rank` is 1–10.
- At least one of `dense_rank` or `lexical_rank` is present.
- `fusion_score` is finite and present.
- `candidate_origin = RETRIEVAL`.
- `hierarchy_depth = 0`.
- `hierarchy_relation`, primary anchor fields are null.
- `hierarchy_anchor_references` is normally empty. If the same chunk was rediscovered structurally, references may be retained only in a separate debug discovery field; the canonical candidate remains RETRIEVAL.

### HIERARCHY_CHILD candidate

- `retrieval_final_rank`, `dense_score`, `dense_rank`, `lexical_score`, `lexical_rank`, and `fusion_score` are all null.
- `candidate_origin = HIERARCHY_CHILD`.
- `hierarchy_relation = DIRECT_CHILD`.
- `hierarchy_depth = 1`.
- `legal_unit_id`, all primary anchor fields, and at least one anchor reference are present.
- The primary anchor fields equal the first sorted anchor reference.
- The child document equals every anchor reference's document as verified from stored rows.

### Combined stream

- `chunk_id` values are unique.
- `context_candidate_order` is exactly `1..N`, with no gaps or duplicates.
- Base anchor `retrieval_final_rank` values remain unchanged.
- Candidate order follows anchor, accepted direct children, next anchor.
- All candidate documents satisfy the validated request filter.
- All public content/provenance originates from the authoritative `chunks` row.

## Dedup contract

Dedup key: `chunk_id`.

1. Load the base Top 10 into the identity map first.
2. A child already present as a base result is skipped; base scores and RRF rank win.
3. A child found from multiple anchors is emitted once.
4. Choose its primary anchor by `(anchor_retrieval_final_rank, anchor_chunk_id)`.
5. Retain all unique anchor references in that same deterministic order.
6. Do not fuzzy-deduplicate or merge content in Block 4.

Block 5's existing normalized-content-per-document dedup remains a separate later-stage invariant.

## Block 5 compatibility amendment

The future implementation minimally amends `SelectedEvidence`:

```python
class SelectedEvidence(BaseModel):
    # Existing fields remain.
    retrieval_final_rank: int | None
    context_candidate_order: int
    candidate_origin: CandidateOrigin
    hierarchy_relation: HierarchyRelation | None
    anchor_chunk_id: str | None
    anchor_retrieval_final_rank: int | None
    dense_score: float | None
    dense_rank: int | None
    lexical_score: float | None
    lexical_rank: int | None
    fusion_score: float | None
```

Block 5 input validation changes only as follows:

- validate strictly increasing `context_candidate_order` instead of assuming every item has an increasing RRF rank;
- allow retrieval ranks/scores to be null exactly for `HIERARCHY_CHILD`;
- validate origin-specific invariants above.

Unchanged Block 5 behavior: sequence preservation, exact normalized-content dedup, `S1..Sn`, exact TokenCounter, whole chunks, Greedy Stop, no truncation, 4,096-token budget, and provenance preservation.

## Debug trace amendment

The future `RetrievalSnapshot` adds explicit arrays:

```python
rrf_candidates: list[CandidateSnapshot]          # immutable base Top 10
hierarchy_candidates: list[HierarchyCandidateSnapshot]
final_context_candidates: list[EnrichedCandidateSnapshot]
```

`HierarchyCandidateSnapshot` contains:

```python
chunk_id: str
document_id: str
legal_unit_id: str
candidate_origin: Literal["HIERARCHY_CHILD"]
hierarchy_relation: Literal["DIRECT_CHILD"]
hierarchy_depth: Literal[1]
anchor_chunk_id: str
anchor_legal_unit_id: str
anchor_retrieval_final_rank: int
hierarchy_anchor_references: list[HierarchyAnchorReference]
context_candidate_order: int
content_preview: str
```

Request-level debug configuration is display-only:

```python
hierarchy_config: {
    "enabled": bool,
    "max_anchors": int,
    "max_children_per_anchor": int,
    "max_candidates_added": int,
    "depth": 1,
}
```

The Debug Cockpit must not mutate these settings.

## Public request and Block 6

- No hierarchy fields or controls are added to `AnswerRequest` or public `RetrievalRequest`.
- Block 6 schemas, prompt, provider, citations, answerability marker, and SSE contract do not change.
- Citations continue to resolve from selected `source_id` to the original chunk/document metadata and provenance.
