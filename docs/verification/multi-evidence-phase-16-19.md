# Multi-Evidence Phases 16–19 — Real Block 5 and Context Risk

Status: **PASS**

Every replay strategy was fed through the real frozen Block 5 service with the production Qwen tokenizer and 4,096-token budget.

For H2 direct-child expansion:

- Average input candidates: 13.36.
- Average selected candidates: 12.64.
- Average context tokens: 2,416.7 (59.00% utilization).
- Budget exhaustion: 11/55.
- Retrieved expected evidence dropped: 0.
- Multi-piece context completeness: 6/9 (66.67%).

Broader hierarchy strategies demonstrated the ordering/budget risk: H3, H4, H7, and H7+wider-15 each had one retrieved-then-dropped expected-evidence case. H2 did not exhibit this regression in the frozen corpus.

Temporary grouping diagnostic:

- Mean tokens before: 1,922.6.
- Mean tokens after: 1,768.6.
- Mean savings: 154 tokens (8.0%).
- Per-case effect ranged from 56.7% savings to 26.6% inflation.

No Block 5 code, budget, ordering, or persisted chunk representation changed.

Detailed evidence: `evaluation/reports/multi_evidence_context_simulation_v1.json` and `.md`.

