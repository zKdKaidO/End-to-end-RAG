# Legal Hierarchy Retrieval V2 — Failure and Fallback Contract

Status: **ACTIVE FALLBACK CONTRACT — RE-FROZEN**

## Principle

Hierarchy enrichment is optional structural recall over an already valid, hydrated base Top 10. Expected absence of hierarchy is not an error. When base retrieval remains correct and available, an enrichment-only failure falls back to the base stream and is made explicit in diagnostics. No Redis/RQ job, retry, or asynchronous workflow is introduced.

## Decision table

| Condition | Action | Diagnostic | HTTP impact |
|---|---|---|---|
| Anchor has no `legal_unit_id` | Keep anchor; do not expand it | stage `HIERARCHY_ANCHOR_SELECTION`; reason `NO_LEGAL_UNIT`; increment `anchors_without_legal_unit` | None; continue 200 |
| Multiple anchors share one legal unit | Use earliest RRF anchor for lookup; retain all anchor references | `DUPLICATE_ANCHOR_UNIT_COLLAPSED` | None |
| Anchor unit has no direct children | Keep anchor; no expansion | status `NO_EXPANSION`; reason `LEAF_UNIT` | None |
| Direct child unit has no chunks | Skip that unit; retain other valid children | `CHILD_UNIT_WITHOUT_CHUNKS`, child unit ID | None; warning log |
| Child has multiple chunks | Consider all chunks in deterministic `chunk_index`, `chunk_id` order, subject to caps | `child_chunks_examined` | None |
| Child already exists in base Top 10 | Keep base candidate and original scores/rank; do not add duplicate | `BASE_CANDIDATE_WINS`, increment duplicate count | None |
| Same child found through multiple anchors | Emit once; primary anchor is lowest RRF rank/UUID; record all anchors | `MULTIPLE_ANCHOR_DISCOVERY` | None |
| Child document differs from anchor document | Reject child as invalid stored relationship | `DOCUMENT_RELATIONSHIP_MISMATCH`; structured error with IDs | Baseline fallback, normally 200; alert |
| Child conflicts with request `document_ids` | SQL excludes it; in-memory invariant check rejects any leakage | `DOCUMENT_FILTER_REJECTED`; increment filter rejection | None if safely rejected; invariant alert |
| Per-anchor child cap reached | Stop adding children for that anchor after source-order selection | `PER_ANCHOR_CAP_REACHED` | None |
| Global added-candidate cap reached | Stop expansion deterministically; keep already ordered candidates and all base anchors | `GLOBAL_CAP_REACHED`; `hierarchy_cap_reached=true` | None |
| Malformed/cyclic stored parent relation | Because V2 is one hop, never traverse recursively; reject self-parent or inconsistent row | `INVALID_PARENT_RELATION` | Baseline fallback, normally 200; alert |
| Hierarchy SQL validation/programming error | Do not emit partial children; return base anchors | status `BASELINE_FALLBACK`; stage `HIERARCHY_LOOKUP` | 200 only when base anchors are already hydrated and session recovery succeeds; otherwise existing 500 |
| PostgreSQL unavailable during hierarchy lookup | Attempt no application retry; preserve already hydrated base anchors if safe | status `BASELINE_FALLBACK`; dependency error and timing | 200 fallback when safe; otherwise existing 503 |
| Child hydration field missing/invalid | Reject affected child; do not invent metadata/provenance | stage `HIERARCHY_HYDRATION`; `INVALID_CHILD_CHUNK` | Base/remaining valid candidates continue; alert |
| Dedup/order invariant fails | Discard entire enrichment result and emit base anchors | stage `HIERARCHY_DEDUP` or `HIERARCHY_ORDERING`; status `BASELINE_FALLBACK` | 200 fallback; internal error log |
| Block 5 later reaches token budget | Frozen Greedy Stop at whole-chunk boundary | existing `TOKEN_BUDGET`; hierarchy origin/order visible for dropped suffix | None; existing 200 behavior |
| First evidence exceeds context budget | Existing Block 5 behavior | existing `TOP_EVIDENCE_EXCEEDS_CONTEXT_BUDGET` | None; existing insufficient-evidence path |

## Status model

```python
class HierarchyExpansionStatus(str, Enum):
    DISABLED = "DISABLED"
    EXPANDED = "EXPANDED"
    NO_EXPANSION = "NO_EXPANSION"
    BASELINE_FALLBACK = "BASELINE_FALLBACK"
```

Request-level diagnostics:

```python
class HierarchyExpansionDiagnostics(BaseModel):
    status: HierarchyExpansionStatus
    stage: str | None
    reason_codes: list[str]
    base_anchor_count: int
    unique_anchor_unit_count: int
    anchors_expanded: int
    anchors_without_legal_unit: int
    children_examined: int
    candidates_added: int
    duplicate_count: int
    document_filter_rejection_count: int
    per_anchor_cap_count: int
    global_cap_reached: bool
    lookup_ms: float
    total_ms: float
```

Reason codes are stable machine identifiers, never inferred from exception message text.

## Stage mapping

| Stage | Responsibility |
|---|---|
| `HIERARCHY_ANCHOR_SELECTION` | Validate ordered base anchors, legal-unit IDs, and unique-unit collapse |
| `HIERARCHY_LOOKUP` | Execute the one parameterized bulk query and validate returned relations/documents |
| `HIERARCHY_HYDRATION` | Validate authoritative child content, metadata, and provenance |
| `HIERARCHY_DEDUP` | Apply chunk-ID identity and base-wins/multiple-anchor rules |
| `HIERARCHY_ORDERING` | Enforce caps and assign gapless `context_candidate_order` |

## Partial-result rule

The expander is atomic at the enrichment level. It may skip an individually malformed child while retaining other independently valid children only when the row can be safely isolated and the relationship/document invariants remain known. A query-wide exception, inconsistent ordering, or dedup invariant discards all hierarchy additions and returns the base stream. This prevents silent partially ordered evidence.

## Security and privacy

- Do not log full document text or embedding vectors.
- Log IDs, unit types/numbers, counts, stage/reason, and bounded content previews only in authorized debug traces.
- Document filtering is parameterized inside SQL and checked in memory.
- Hierarchy configuration is server-owned and read-only in Debug Cockpit.
