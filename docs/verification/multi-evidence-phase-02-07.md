# Multi-Evidence Phases 02–07 — Cases, Coverage, Taxonomy, and Hierarchy

Status: **PASS**

- Multi-piece cases were derived from frozen Evaluation V2 semantics; no count was hardcoded.
- Derived cases: 9; declared required evidence references: 26.
- Each case records question/category/filter, acceptable sets, required documents/chunks, production dense/lexical/fused ranks, Block 5 selection, Block 6 status, and citations.
- Candidate coverage: Dense/Fused Top 10 = 10/26, Top 20 = 12/26, Top 30 = 14/26, Top 50 = 19/26; Lexical Top 10–50 = 0/26; absent from both branch pools = 7/26.
- Only 3/9 complete acceptable solutions exist in the frozen candidate pools, establishing a perfect-reranker complete-case ceiling of 33.33%.
- All nine multi-piece cases had the expected document represented in Top 10. The dominant case-level pattern was intra-document legal-unit discrimination.
- Missing-piece taxonomy is overlapping: candidate generation 7, dense representation 7, lexical joint-pool miss 7, fusion ranking 9, final cutoff 9, intra-document ranking 16, hierarchy fragmentation 12, multiple 16.
- Frozen hierarchy relationships across evidence sets: same article 6, sibling 6, adjacent legal unit 6, same document 8, cross-document 1.
- Hierarchy recovery ceiling: 12/16 missing references (75%) were related to a retrieved anchor; 4/16 were not.

Detailed evidence:

- `evaluation/reports/multi_evidence_candidate_coverage_v1.json`
- `evaluation/reports/multi_evidence_candidate_coverage_v1.md`
- `evaluation/reports/multi_evidence_hierarchy_analysis_v1.json`
- `evaluation/reports/multi_evidence_hierarchy_analysis_v1.md`

