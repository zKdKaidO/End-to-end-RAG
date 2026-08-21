# Evidence Presentation + Status/Citation Stability Experiment V1 — Final Audit

## Result

**COMPLETE — READY FOR TARGETED DESIGN**

Production changed: **NO**. The production prompt remains `legal-rag-v2`.

## Measured decision

The best measured combination was compact few-shot prompt + P1 structural
anchor/child presentation:

- answerable acceptance: 87.27% frozen baseline → 94.55%
- false abstention: 12.73% → 5.45%
- citation validity: 87.27% → 94.55%
- expected-source match: 85.45% → 92.73%
- status validity: 100%
- unanswerable abstention: 10/10
- unsupported direct answers: 0
- prompt tokens: -144.3 mean
- TTFT: -288.4ms mean
- generation time: -386.4ms mean

Compact prompt + unchanged P0 independently passed the full acceptance rules
(92.73% acceptance, 90.91% grounded expected-source, 10/10 safety). Current
legal-rag-v2 + P1 also passed but was weaker (89.09%). The primary next target
is therefore **LEGAL-RAG-V3 DESIGN**, with P1 retained as a secondary candidate
for that future design phase.

## Key diagnostics

- Production targeted repeats: 3/12 answerable/grounded; three stable false
  abstentions; cross-document historical failure not reproduced.
- P1 presentation-only targeted result: 6/12 grounded.
- Compact prompt variants targeted result: 9/12 grounded.
- `v2_civil_scope` remained 0/3 under all production-plausible target variants;
  it retains strong case-specific distractor evidence.
- Context length did not separate failures overall (r = -0.056).
- Previous combined-prompt duplicate marker reproduced identically 3/3 in raw
  provider output. The strict parser correctly rejected it and was unchanged.
- Best multi-evidence expected-source grounding: 77.78%; hierarchy-recovered
  5/5; multi-document 1/1.

## Architecture audit

- Blocks 1–6: unchanged
- Hierarchy Retrieval V2: unchanged
- Block 5 evidence selection/budget: unchanged
- production prompt: legal-rag-v2
- second LLM/classifier/reranker/query rewrite: none
- schema drift: none
- new database tables: 0
- experiment records: 545 real local-provider generations

## Regression

- backend: 235 collected, 235 passed, 0 failed, 8 warnings, 88.72s
- frontend: 11 passed, 0 failed
- frontend build: PASS

## Artifacts

- `evaluation/reports/evidence_presentation_experiment_v1.md`
- `evaluation/reports/evidence_presentation_experiment_v1.json`
- `evaluation/reports/evidence_presentation_strategy_comparison_v1.md`
- `evaluation/reports/evidence_presentation_strategy_comparison_v1.json`
- `evaluation/reports/evidence_presentation_baseline_v1.md`
- `evaluation/reports/evidence_presentation_baseline_v1.json`
- `evaluation/reports/context_distraction_analysis_v1.md`
- `evaluation/reports/status_marker_failure_analysis_v1.md`
- `evaluation/reports/citation_fading_analysis_v1.md`
- `evaluation/reports/evidence_presentation_safety_v1.md`

No experimental prompt or presentation was deployed.

