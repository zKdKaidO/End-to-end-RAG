# Hierarchy V2 Phases 26–36 — Real Evaluation, Safety, and Performance

Status: **PASS WITH MEASURED LIMITATIONS**

The unchanged 65-case Evaluation V2 dataset ran through real PostgreSQL, production hierarchy retrieval, frozen Block 5, real qwen3.5:9b, and legal-rag-v2.

Same-run immutable base → production Top-10:

- Hit@1: 61.82% → 61.82%.
- Hit@10: 85.45% → 90.91%.
- MRR@10: 0.6980 → 0.7062.
- Multi-evidence complete@10: 33.33% → 66.67%.
- Required-evidence recall@10: 46.67% → 80.56%.
- Full expanded-stream multi completeness: 77.78%; required recall: 83.33%.

Historical absolute H2 values differ by at most one answerable case because additional canonical test indexes now coexist in the persistent development database. Same-run attribution proves Hit@1 preservation and approximate H2 parity without changing the frozen dataset or production retrieval controls.

Context: answerable-case mean tokens 2,096.2 → 2,385.3; budget exhaustion 0/55 → 11/55; expected-evidence retention remained 100%; retrieved-but-dropped remained 0.

Safety: all 10 unanswerable cases returned `INSUFFICIENT_EVIDENCE`; unsupported direct answers 0/10. Four answerable cases with complete context abstained, which remains a separate Block 6 calibration issue and was not changed here.

Candidate inflation: average base/added/combined 10.00/4.09/14.09; p95 added 12; 46/65 queries expanded; per-anchor cap on 12 queries; global cap on 1; bounds violations 0. Fallback fault injection preserved the complete base stream.

Hierarchy latency mean/p50/p95: lookup 3.227/2.900/4.963 ms; total 3.538/3.203/5.578 ms. Representative `EXPLAIN ANALYZE` execution was 2.521 ms. No new index was warranted.

Detailed evidence is in the four `legal_hierarchy_v2_*` evaluation reports and the false-abstention observation.

