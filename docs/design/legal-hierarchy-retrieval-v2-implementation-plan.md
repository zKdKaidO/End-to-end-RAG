# Legal Hierarchy Retrieval V2 — Implementation Audit Record

Status: **EXECUTED — PASS; SEE VERIFICATION ARTIFACTS**

## Proposed repository fit

Current retrieval code is already separated into schemas, domain types, repository, fusion, and service modules. The future implementation should add only:

```text
app/retrieval/
  hierarchy_expander.py       # bounded pure merge/dedup/order rules
  hierarchy_repository.py     # one parameterized bulk lookup
  hierarchy_types.py          # origin/relation/diagnostic domain types
```

Amend existing files narrowly:

- `app/retrieval/schemas.py`: enriched boundary DTO.
- `app/retrieval/service.py`: invoke expander after base Top 10 hydration.
- `app/context/schemas.py` and `app/context/service.py`: consume `context_candidate_order` and nullable hierarchy diagnostics.
- `app/debug/schemas.py` and `app/debug/services.py`: distinct hierarchy stage and final candidate order.
- `app/core/config.py`: server-owned bounds only.

Do not restructure Dense, Lexical, RRF, query embedding, answer orchestration, Block 6, queues, or public request schemas.

## Phase 01 — Baseline and immutable inputs

- Verify Evaluation V1 and V2 hashes.
- Run the then-current backend/frontend baseline.
- Record PostgreSQL table/index inventory and current production retrieval defaults.
- Verify canonical indexes are `block3-v1`.
- Stop on any failed regression or hash mismatch.

## Phase 02 — Candidate schema amendment

- Add `CandidateOrigin`, `HierarchyRelation`, anchor reference, and enriched candidate schemas.
- Preserve RRF value as `retrieval_final_rank`.
- Add strictly increasing `context_candidate_order`.
- Make retrieval diagnostics nullable only for hierarchy children.
- Add origin-specific validators; do not fabricate scores.

## Phase 03 — Bulk hierarchy lookup

- Implement one parameterized query over `chunks` and `legal_units`.
- Apply the validated document filter inside SQL.
- Order rows by anchor priority, child legal source position, and chunk order.
- Capture `EXPLAIN (ANALYZE, BUFFERS)` and lookup timing.
- Prove no N+1 behavior with query-count assertions.
- Add no table/index unless measured evidence separately justifies it.

## Phase 04 — Bounded direct-child expansion

- Select only base RRF Top 10 anchors.
- Collapse duplicate legal-unit anchors deterministically.
- Enforce 10 anchors, 4 children/anchor, 20 added globally, depth 1.
- Reject recursion, parent/sibling/article/adjacency expansion.
- Preserve document identity and filter.

## Phase 05 — Dedup and total ordering

- Dedup by `chunk_id` before Block 5.
- Base retrieval candidate wins.
- Retain deterministic multiple-anchor diagnostics.
- Implement anchor → children → next anchor ordering.
- Assign gapless `context_candidate_order` without changing RRF rank.

## Phase 06 — Block 5 compatibility

- Validate candidate order rather than requiring non-null RRF rank for every candidate.
- Preserve exact normalized-content dedup, S numbering, TokenCounter, whole chunks, Greedy Stop, no truncation, budget, and provenance.
- Prove hierarchy metadata is carried diagnostically but omitted from user-facing evidence text unless already part of authoritative metadata.
- Do not increase the 4,096-token budget.

## Phase 07 — Debug observability

- Add RRF Top 10, Hierarchy Expansion, and Final Context Candidate Order snapshots.
- Add hierarchy counts/status/reasons and lookup/total timings.
- Ensure authorized debug responses contain no prompts, secrets, vectors, or uncontrolled full documents.
- Do not implement frontend changes in the retrieval backend phase unless separately approved.

## Phase 08 — Deterministic unit tests

Required cases:

- anchor without `legal_unit_id`;
- anchor unit without children;
- one direct child;
- multiple direct children ordered by legal position;
- child legal unit containing multiple chunks;
- duplicate child discovered by multiple anchors;
- child already present in base retrieval;
- duplicate anchor legal units;
- document-filter preservation and hostile UUID input handled upstream;
- child/anchor document mismatch;
- per-anchor and global expansion caps;
- gapless stable ordering;
- base RRF ranks unchanged;
- hierarchy scores/ranks remain null;
- one-hop only, including a grandchild fixture that must not appear;
- bulk lookup query count equals one;
- provenance/content integrity;
- graceful baseline fallback;
- Block 5 origin/order compatibility;
- budget stop and no truncation;
- later cross-document anchor remains reachable.

## Phase 09 — Targeted frozen V2 replay

Use real canonical Corpus V2 cases:

- direct-fact baseline pass: one single-evidence case that needs no expansion;
- hierarchy-recoverable multi-evidence case: at least `v2_bank_loan_limit_exceptions` or an equivalent frozen case;
- cross-document case: `v2_cross_document_effective_dates`;
- no-expansion leaf/no-unit case;
- hard unanswerable case;
- context-pressure case with multiple children.

Record base anchors, legal units, children examined/added, dedup, candidate order, Block 5 selection, and token budget.

## Phase 10 — Full frozen V2 evaluation

Run all 65 unchanged cases and report:

- multi-evidence complete retrieval;
- required-evidence recall;
- Hit@1/3/5/10 and MRR;
- single-evidence Hit@10;
- Document Hit@1/3/5/10 and wrong-document rate;
- context completeness;
- retrieved-but-dropped expected evidence;
- budget exhaustion;
- cross-document retention;
- hierarchy lookup latency and candidate inflation.

Implementation parity targets are measurements, not SLAs:

- approximately 66.67% multi-evidence completeness;
- approximately 81.11% evidence recall;
- approximately 92.73% Hit@10;
- preserve 63.64% Hit@1;
- zero expected-evidence context loss.

Do not hardcode or weaken ground truth to meet them.

## Phase 11 — Real Block 4→5→6 generation replay

- Use real qwen3.5:9b and unchanged `legal-rag-v2`.
- Replay the affected multi-evidence cases and all ten unanswerable cases.
- Measure answerability status, citation presence/validity/source match, multi-evidence citation completeness, false abstention, unsupported answers, TTFT, generation, and total latency.
- Mandatory safety: 10/10 correct unanswerable abstentions, unsupported-answer rate 0, citation provenance exact, no-secrets/debug behavior unchanged.
- Keep false-abstention attribution separate from retrieval success.

## Phase 12 — Restart and full regression

- Restart API/PostgreSQL without deleting volumes.
- Verify hierarchy config and canonical model cache survive.
- Verify no new table/schema drift unless separately approved.
- Verify `/retrieve`, `/answer`, `/answer/stream`, and `/internal/debug/rag` contracts.
- Run complete backend tests, frontend tests/build, and both frozen hash checks.
- Required: zero failures.

## Acceptance gates

Engineering gates:

- direct-child only and depth 1;
- all bounds server-owned;
- no fake Dense/Lexical/RRF fields;
- base RRF ranks preserved;
- deterministic candidate order;
- `chunk_id` dedup and base-wins rule;
- document filter in bulk SQL;
- one hierarchy query, no N+1;
- zero new production tables;
- graceful baseline fallback is observable;
- Block 5 budget and Greedy Stop unchanged;
- Block 6/SSE/prompt/provider unchanged;
- no reranker, embedding, LLM, Redis, or RQ added;
- all frozen regression and safety tests pass.

Quality gates are measured against baseline and require human review. The H2 values above are parity targets, not automatic production-readiness thresholds.

## Out of scope

- recursive hierarchy traversal;
- parent/sibling/article/adjacency expansion;
- grouped legal-unit context;
- reranking;
- query rewriting;
- metadata-aware retrieval;
- false-abstention calibration;
- frontend implementation.
