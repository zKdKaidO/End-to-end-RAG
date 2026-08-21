# Legal Hierarchy Retrieval V2 — Final Verification

Status: **PASS — READY TO RE-FREEZE**

## Frozen inputs

- Evaluation V1: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245` (unchanged).
- Evaluation V2: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842` (unchanged).
- Canonical index version: `block3-v1`; the three evaluation documents retained 965/965 active indexes after restart.

## Implementation audit

The amendment is a server-owned `LegalHierarchyExpander` after immutable RRF Top 10 and base hydration. It performs one parameterized, one-hop direct-child query, authoritative child hydration in the same query, UUID dedup, deterministic anchor→children ordering, and atomic baseline fallback.

Hard limits: 10 anchors, 4 emitted children/anchor, 20 added candidates, 30 combined candidates, depth 1. No public request or debug tuning controls exist. No fake IR score or rank is assigned to a structural child.

Block 5 consumes the explicit context order and accepts hierarchy-null IR diagnostics; all selection/budget/provenance invariants remain frozen. Block 6 and legal-rag-v2 are unchanged.

## Real Evaluation V2

The unchanged 65 cases ran through real PostgreSQL, Block 4 hierarchy retrieval, Block 5, qwen3.5:9b, and legal-rag-v2.

| Metric | Historical before | Real hierarchy run |
|---|---:|---:|
| Hit@1 | 63.64% | 61.82% |
| Hit@3 | 74.55% | 72.73% |
| Hit@5 | 83.64% | 87.27% |
| Hit@10 | 85.45% | 90.91% |
| MRR | 0.7087 | 0.7089 |
| Full-stream multi completeness | 33.33% | 77.78% |
| Full-stream required-evidence recall | 46.67% | 83.33% |

Historical absolute metrics include base-RRF drift from additional canonical test indexes in the persistent development DB. Attribution-safe same-run base→hierarchy metrics are Hit@1 61.82%→61.82%, Hit@10 85.45%→90.91%, MRR@10 0.6980→0.7062, multi complete@10 33.33%→66.67%, and required recall@10 46.67%→80.56%. This passes the approved approximate H2 parity rule within one answerable case.

Context expected-evidence retention stayed 100% with zero retrieved-expected drops. Answerable mean context tokens increased from 2,096.2 to 2,385.3 and budget exhaustion from 0/55 to 11/55, matching the known context-inflation tradeoff.

Generation measured 87.27% answer/citation presence, 87.27% citation structural validity, 85.45% expected-source match, 0% missing citations, and 0% invalid citations. All 10 unanswerable cases abstained and unsupported direct answers remained 0. Four answerable complete-context cases abstained; that remains outside this retrieval amendment.

## Performance and bounds

- Hierarchy lookup mean/p50/p95: 3.227/2.900/4.963 ms.
- Hierarchy total mean/p50/p95: 3.538/3.203/5.578 ms.
- Representative query plan execution: 2.521 ms; no index added.
- Average base/added/combined: 10.00/4.09/14.09; p95 children: 12.
- Per-anchor/global cap query counts: 12/1.
- Bounds violations: 0; hierarchy fallbacks in real run: 0.
- Controlled lookup-failure test: baseline Top 10 preserved with visible fallback.

## Regression and restart

- Backend: 230 collected, 230 passed, 0 failed, 8 warnings; final rerun 90.34 seconds (preceded by the requested verbose run at 90.91 seconds).
- Frontend: 11 passed, 0 failed; production build PASS (30 modules, 149 ms).
- Non-destructive restart: PostgreSQL/API/frontend PASS; persistent data/indexes, retrieval, Ask generation, DebugTrace, evaluation artifacts, and provider reconnection PASS.
- PostgreSQL production tables: 10 before and after; new tables: 0.

## Architecture drift

Blocks 1 and 3 are unchanged. Block 2 retains only its previously approved index-version repair. Dense, lexical, RRF, base Top 10, Block 5 strategy/budget, Block 6, embedding, prompt, provenance mapping, SSE, Redis/RQ, and schema are unchanged. The only active amendments are bounded direct-child Block 4 enrichment, explicit enriched candidate ordering/diagnostics, and minimal Block 5/debug/evaluation compatibility.

## Evidence

- `docs/verification/hierarchy-v2-phase-01.md`
- `docs/verification/hierarchy-v2-phase-02.md`
- `docs/verification/hierarchy-v2-phase-03-20.md`
- `docs/verification/hierarchy-v2-phase-21-25.md`
- `docs/verification/hierarchy-v2-phase-26-36.md`
- `docs/verification/hierarchy-v2-phase-37.md`
- `docs/verification/hierarchy-v2-phase-38.md`
- `docs/verification/hierarchy-v2-phase-39.md`
- `evaluation/reports/legal_hierarchy_v2_retrieval_before_after.{json,md}`
- `evaluation/reports/legal_hierarchy_v2_context.{json,md}`
- `evaluation/reports/legal_hierarchy_v2_generation.{json,md}`
- `evaluation/reports/hierarchy_v2_false_abstention_observation.md`
- `evaluation/reports/legal_hierarchy_v2_latency.md`

## Known limitations

- Context inflation is material even though expected evidence was not dropped.
- Supported-case false abstention remains a separate calibration problem.
- `v2_bank_board_loan_threshold` was not solved by hierarchy; current base retrieval changed independently as persistent canonical test indexes accumulated.
- Only three substantive evaluation documents are frozen; broader-corpus behavior is not established.
- Historical `v1` rows remain intentionally untouched and ignored.
- Persistent canonical test indexes create absolute metric drift; same-run immutable-base comparisons are required for hierarchy attribution.

Final decision: **LEGAL HIERARCHY RETRIEVAL V2 READY TO RE-FREEZE**.
