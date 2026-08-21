# Multi-Evidence Phases 20–27 — Generation, Side Analyses, and Isolation

Status: **PASS**

Real frozen Block 6 replayed H2 on the six multi-piece cases that were incomplete at baseline, using qwen3.5:9b, `legal-rag-v2`, and the unchanged GenerationProfile.

- Completed/ANSWERABLE: 4/6.
- False abstention: 2/6.
- Citation present: 4/6.
- Expected-source match: 3/6.
- Unsupported direct answers: 0.
- TTFT mean/p50/p95: 2,857 / 1,404 / 10,185 ms.
- Generation mean/p50/p95: 4,646 / 3,200 / 12,042 ms.

The two previously measured supported-case false abstentions remain separate from retrieval attribution in `evaluation/reports/false_abstention_side_report_v1.md`. Production Block 6 was not changed.

Wrong-document side audit: `v2_bank_board_loan_threshold` lacked both the expected document and expected chunk in the frozen pool; hierarchy expansion cannot repair a pre-document-selection failure. Metadata-aware retrieval remains a separate, inconclusive future experiment.

Near-duplicate audit: competition was sparse and not the dominant multi-piece failure. One failed case had a near-duplicate pair in Top 10; five did not.

Isolation verification:

- Experiment code is contained under `evaluation/experiments/multi_evidence_v1/`.
- No production service imports the experiment package.
- Production Top-K/RRF, endpoints, Block 5, Block 6, schema, Redis/RQ, and databases are unchanged.
- No production reranker, hierarchy expansion, metadata filter, or query rewrite was added.

Decision: **READY FOR TARGETED RETRIEVAL DESIGN**, with bounded direct-child hierarchy retrieval as the next design target—not a production change in this phase.

