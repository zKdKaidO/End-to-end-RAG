# Multi-Evidence Retrieval Experiment V1

Status: **COMPLETE**. This was an offline diagnostic replay and ablation. Production Blocks 1–6, retrieval defaults, RRF, Block 5, Block 6, database schema, and both frozen evaluation datasets were not changed.

## Frozen inputs

- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Multi-piece cases derived from dataset semantics: 9
- Declared required evidence references analyzed: 26
- Retrieval snapshots: real frozen V2 baseline
- Context simulations: real frozen Block 5, Qwen tokenizer, 4,096-token budget
- Finalist generation: real qwen3.5:9b, `legal-rag-v2`, unchanged GenerationProfile

## Executive finding

The dominant measured failure is legal-hierarchy fragmentation and intra-document legal-unit discrimination, not Block 5 loss and not a reranker-sized ranking problem. Twelve of 16 evidence references missing from production Top 10 were reachable from existing Top-10 anchors through deterministic frozen hierarchy relationships. Direct-child expansion was the smallest and strongest replay:

| Metric | Production baseline | H2 direct children |
|---|---:|---:|
| All-answerable Hit@1 | 63.64% | 63.64% |
| All-answerable Hit@10 | 85.45% | 92.73% |
| MRR | 0.7087 | 0.7217 |
| Multi-piece complete retrieval | 3/9 (33.33%) | 6/9 (66.67%) |
| Multi-piece required-evidence recall | 46.67% | 81.11% |
| Multi-piece complete after Block 5 | 3/9 (33.33%) | 6/9 (66.67%) |
| Expected evidence retrieved then dropped | 0 | 0 |
| Average candidate count | 10.00 | 13.36 |
| Average context tokens | 2,096.2 | 2,416.7 |
| Budget-exhausted cases | 0/55 | 11/55 |

H2 preserved Hit@1 and improved single-evidence Hit@10 from 95.65% to 97.83%. Its wider context cost is material but did not drop expected evidence in this frozen run.

## Candidate coverage and reranker ceiling

| Window | Required evidence present |
|---|---:|
| Dense Top 10 | 10/26 |
| Dense Top 20 | 12/26 |
| Dense Top 30 | 14/26 |
| Dense Top 50 | 19/26 |
| Lexical Top 10/20/30/50 | 0/26 |
| Fused Top 10 | 10/26 |
| Fused Top 20 | 12/26 |
| Fused Top 30 | 14/26 |
| Fused Top 50 | 19/26 |
| Absent from both branch pools | 7/26 |

Only 3/9 multi-piece cases have a complete acceptable evidence set anywhere in the frozen Dense/Lexical candidate pool. Consequently, a perfect reranker over that pool has a 33.33% complete-case ceiling—the same as production Top 10. No reranker was downloaded or tested. **Reranking alone cannot solve the dominant failure.**

## Failure taxonomy

Labels overlap where evidence supports multiple contributing causes; they are not mutually exclusive.

| Label | Missing evidence references |
|---|---:|
| Candidate-generation miss | 7 |
| Dense-representation miss | 7 |
| Lexical-candidate miss at the joint-pool-miss stage | 7 |
| Fusion-ranking miss | 9 |
| Final Top-K cutoff | 9 |
| Intra-document ranking failure | 16 |
| Legal-hierarchy fragmentation | 12 |
| Multiple contributing causes | 16 |

All nine multi-piece cases had the correct document represented in Top 10 and were classified as intra-document legal-unit discrimination at the case level. One separate V2 wrong-document case was a candidate-generation/document-discrimination failure: the expected document and chunk were absent from its frozen pool, so hierarchy expansion could not help.

## Existing hierarchy evidence

Across the nine required evidence sets, the frozen legal graph exposed these relationships (a case/set may contribute more than one relationship):

- Same article: 6
- Same-parent siblings: 6
- Adjacent legal units: 6
- Different legal units in the same document: 8
- Cross-document: 1
- Direct parent/child among required pieces: 0

For production misses, 12/16 (75%) were theoretically recoverable from a current Top-10 anchor via parent, child, sibling, same-article, adjacent-unit, or same-unit relationships. Four were not hierarchy-recoverable.

## Strategy ablation

| Strategy | Avg candidates | Hit@10 | MRR | Multi complete | Evidence recall | Context complete | Budget exhausted |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline Top 10 | 10.00 | 85.45% | 0.7087 | 33.33% | 46.67% | 33.33% | 0 |
| Wider RRF Top 20 | 20.00 | 85.45% | 0.7087 | 33.33% | 46.67% | 33.33% | 23 |
| H1 parent | 15.98 | 83.64% | 0.6895 | 33.33% | 43.89% | 33.33% | 19 |
| **H2 direct children** | **13.36** | **92.73%** | **0.7217** | **66.67%** | **81.11%** | **66.67%** | **11** |
| H3 siblings | 26.33 | 85.45% | 0.7145 | 44.44% | 56.67% | 55.56% | 24 |
| H4 same article | 25.96 | 83.64% | 0.6931 | 33.33% | 52.78% | 44.44% | 22 |
| H5 adjacent unit | 23.82 | 87.27% | 0.6987 | 33.33% | 58.70% | 55.56% | 23 |
| H6 parent + children | 18.82 | 92.73% | 0.7035 | 66.67% | 78.89% | 66.67% | 21 |
| H7 article + adjacency | 27.91 | 85.45% | 0.6889 | 44.44% | 58.33% | 55.56% | 24 |
| Coverage-aware Top 10 | 10.00 | 85.45% | 0.7087 | 33.33% | 46.67% | 33.33% | 0 |
| H7 + wider 15 | 37.09 | 85.45% | 0.6889 | 44.44% | 58.33% | 55.56% | 34 |

Simply widening the final window increased token pressure but did not create another complete multi-piece solution, because the missing pieces were often absent from the fused pool. Coverage-aware selection alone also produced no gain. Broad hierarchy variants added more noise and context pressure than direct-child expansion.

## Context and grouping diagnostic

Real Block 5 retained every expected piece H2 retrieved. H2 increased average budget use from 51.18% to 59.00% and caused 11 budget-exhaustion events, but none excluded expected evidence. Broader hierarchy strategies did produce retrieval-improvement/context-regression behavior: sibling, same-article, article+adjacency, and combined variants each dropped expected evidence in one case.

Temporary grouping by deterministic article/unit reduced average tokens for the nine multi-piece H2 contexts from 1,922.6 to 1,768.6 (154 tokens, 8.0%), but results varied sharply by case: savings ranged from 56.7% to a 26.6% increase. This is future context-design evidence only; it is not a Block 5 proposal and no grouped representation was persisted.

## Finalist generation replay

H2 was replayed through real Block 6 on the six multi-piece cases that were incomplete at production baseline:

- ANSWERABLE/completed: 4/6
- INSUFFICIENT_EVIDENCE false abstentions: 2/6
- Citation present: 4/6
- Expected-source match: 3/6
- Mean multi-evidence citation recall across all six: 63.33%
- TTFT mean / p50 / p95: 2,857 / 1,404 / 10,185 ms
- Generation mean / p50 / p95: 4,646 / 3,200 / 12,042 ms
- Unsupported direct answers observed: 0

The two H2 false abstentions (`v2_social_applicable_groups`, `v2_social_effective_transition`) show that better retrieval does not guarantee answer generation. The previously known supported-case false abstentions (`v2_civil_scope`, `v2_civil_effect_and_repeal`) remain excluded from retrieval attribution and are documented separately.

## Wrong-document and near-duplicate side analyses

`v2_bank_board_loan_threshold` is the one baseline wrong-document case. The expected document was absent from the candidate pool despite identifier metadata being available. This supports a separate metadata/document-aware candidate-generation experiment, but one case is insufficient to justify a production design.

Near-duplicate competition was limited: no near-duplicate pair appeared in Top 10 for five of six failed multi-piece cases; one pair appeared for `v2_bank_loan_limit_exceptions`. It is not the dominant measured cause.

## Recommendation

Recommended next production-design target: **LEGAL HIERARCHY RETRIEVAL V2**, limited initially to bounded direct-child expansion and evaluated with context-budget safeguards. Evidence: 75% hierarchy recoverability ceiling, 3 additional complete multi-piece cases, +34.44 percentage points required-evidence recall, +7.28 points Hit@10, preserved Hit@1, and no expected-evidence drop under H2.

Risks: context inflation, ordering sensitivity under Greedy Stop, ambiguous source granularity, and 2/6 finalist false abstentions. Architecture impact is **MEDIUM** because hierarchy expansion changes retrieval candidate semantics and must be coordinated with Block 5 budget behavior. Confidence is **MEDIUM**: the effect is strong but measured on only nine multi-piece cases and three usable documents.

The index-version audit separately found a genuine frozen-contract integration defect: the automatic Block 2 completion hook creates `v1` jobs while the canonical endpoint and Block 4 use `block3-v1`. Experiment data were already canonical, so no correction was made in this diagnostic phase. The future minimal correction is to use one shared canonical index-version constant in the automatic hook and endpoint, with a regression test.

## Audit artifacts

- `multi_evidence_candidate_coverage_v1.json` / `.md`: all cases, pieces, branch ranks, fused ranks, labels, and document-rank diagnostics.
- `multi_evidence_hierarchy_analysis_v1.json` / `.md`: legal-unit relationships and recovery ceiling.
- `multi_evidence_strategy_comparison_v1.json` / `.md`: complete strategy metrics, side analyses, and real finalist generation records.
- `multi_evidence_context_simulation_v1.json` / `.md`: all Block 5 simulations and grouped-token diagnostic.
- `false_abstention_side_report_v1.md`: supported-case abstention review package.

Final decision: **READY FOR TARGETED RETRIEVAL DESIGN**. No production retrieval fix was implemented.
