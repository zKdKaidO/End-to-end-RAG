# Multi-Evidence Phases 08–15 — Offline Retrieval Replays

Status: **PASS**

Tested against all 55 frozen answerable cases:

- Baseline Top 10 and diagnostic RRF windows 15/20/30/50.
- H1 parent, H2 direct children, H3 siblings, H4 same article, H5 adjacent unit, H6 parent+children, H7 article+adjacency.
- Coverage-aware Top 10 and H7+wider-15.
- Expansions were bounded to four related chunks per anchor and 40 total candidates; entire documents were never expanded.

Best measured strategy: **H2 direct children**.

- Multi-piece complete retrieval: 3/9 → 6/9.
- Multi-piece average evidence recall: 46.67% → 81.11%.
- All-answerable Hit@10: 85.45% → 92.73%.
- MRR: 0.7087 → 0.7217.
- Hit@1: unchanged at 63.64%.
- Single-evidence Hit@10: 95.65% → 97.83%.
- Average candidates: 10.00 → 13.36.

Wider windows alone did not improve complete multi-piece Top-10 retrieval. Coverage-aware selection alone was neutral. Broad hierarchy variants introduced more candidate and context inflation than H2.

Reranker: **NOT TESTED**. The perfect reranker ceiling equals baseline complete retrieval (3/9), so a model download was not technically justified. Reranking alone cannot recover the seven evidence references missing from both pools.

Detailed evidence: `evaluation/reports/multi_evidence_strategy_comparison_v1.json` and `.md`.

