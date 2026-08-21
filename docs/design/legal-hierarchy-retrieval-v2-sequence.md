# Legal Hierarchy Retrieval V2 — Sequence and Data Flow

Status: **ACTIVE PRODUCTION FLOW — RE-FROZEN**

## Production sequence

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant AO as Answer Orchestrator
    participant B4 as Block 4 Retrieval
    participant DE as Query Embedder
    participant DS as Dense Search
    participant LS as Lexical Search
    participant RRF as Python RRF
    participant DB as PostgreSQL
    participant HE as LegalHierarchyExpander
    participant B5 as Block 5 Context Builder
    participant B6 as Block 6 Generation

    Client->>AO: POST /answer or /answer/stream
    AO->>B4: validated query + optional document_ids
    B4->>DE: "query: " + query text
    DE-->>B4: normalized 768-D vector

    B4->>DS: Dense Top 50, canonical block3-v1
    DS->>DB: HNSW cosine query + document filter
    DB-->>DS: dense candidates/ranks
    DS-->>B4: Dense Top 50

    B4->>LS: Lexical Top 50
    LS->>DB: GIN/tsvector query + document filter
    DB-->>LS: lexical candidates/ranks
    LS-->>B4: Lexical Top 50

    B4->>RRF: dense + lexical, unchanged rrf_k
    RRF-->>B4: immutable base RRF Top 10 anchors
    B4->>DB: one bulk hydration for base Top 10
    DB-->>B4: hydrated base chunks + legal_unit_id

    B4->>HE: ordered hydrated anchors + document filter + server bounds
    HE->>HE: select/collapse up to 10 unique anchor units
    HE->>DB: one parameterized bulk direct-child lookup
    DB-->>HE: child units + hydrated child chunks
    HE->>HE: enforce one hop, per-anchor 4, global added 20
    HE->>HE: chunk_id dedup + deterministic anchor/child order
    HE-->>B4: enriched candidates + hierarchy diagnostics

    B4-->>AO: candidate_origin + retrieval_final_rank + context_candidate_order
    AO->>B5: enriched candidate stream, unchanged 4096 budget
    B5->>B5: exact dedup, S assignment, token counting, Greedy Stop
    B5-->>AO: ContextPackage with selected provenance
    AO->>B6: legal-rag-v2 messages
    B6-->>AO: answerability marker + answer + citations
    AO-->>Client: existing response/SSE contract
```

If hierarchy enrichment fails after base hydration, `LegalHierarchyExpander` returns a diagnostic baseline fallback and Block 4 emits the unchanged base Top 10. No retry queue or second request is introduced.

## Data flow

```mermaid
flowchart TD
    Q[Query] --> D[Dense Top 50]
    Q --> L[Lexical Top 50]
    D --> R[Python RRF]
    L --> R
    R --> T[Base RRF Top 10]
    T --> H[Bulk-hydrated Base Anchors]
    H --> E[Bounded Direct-Child Expansion<br/>one hop, existing legal_units.parent_unit_id]
    E --> U[chunk_id Dedup]
    U --> O[Deterministic Context Candidate Ordering]
    O --> C[Block 5 Context Builder<br/>unchanged 4096-token Greedy Stop]
    C --> G[Block 6 Generation]

    T -. immutable .-> RR[retrieval_final_rank<br/>base candidates only]
    O -. new .-> CO[context_candidate_order<br/>all candidates]
    E -. diagnostic .-> OR[candidate_origin / anchor / DIRECT_CHILD]
```

## Rank and order distinction

```text
retrieval_final_rank
    Source: unchanged RRF Top 10
    Domain: 1..10 for RETRIEVAL; null for HIERARCHY_CHILD
    Meaning: ranking evidence from Dense/Lexical fusion

context_candidate_order
    Source: deterministic post-hierarchy merge
    Domain: 1..N for every candidate
    Meaning: exact sequence consumed by Block 5
```

No hierarchy child receives a dense, lexical, fusion, or RRF score/rank.

## Debug diagnostic stages

```mermaid
flowchart LR
    A[Dense] --> C[RRF Top 10]
    B[Lexical] --> C
    C --> D[Hierarchy Anchor Selection]
    D --> E[Hierarchy Bulk Lookup]
    E --> F[Hierarchy Dedup]
    F --> G[Final Context Candidate Order]
    G --> H[Block 5 Selection]
    H --> I[Block 6]
```

The future DebugTrace shows every stage independently. Frontend implementation is explicitly deferred.
