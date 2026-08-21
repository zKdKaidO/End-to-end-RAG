# Corpus V2 Phase 05 — Real Evaluation Baseline

Date: 2026-08-19

Result: **PASS as a measurement run**. No quality threshold was enforced.

The immutable 65-case dataset ran sequentially through real PostgreSQL, Block 4, Block 5, Block 6, Ollama `qwen3.5:9b`, and production `legal-rag-v2`.

Key results:

- Retrieval Hit@1/3/5/10: 63.64% / 74.55% / 83.64% / 85.45%; MRR 0.7087.
- Document Hit@1/3/5/10: 96.36% / 98.18% / 98.18% / 98.18%.
- Multi-evidence (including the multi-document case): complete 33.33%, partial 33.33%, average required-evidence recall 46.67%.
- Lexical: 24.62% non-empty; 0 strict, 16 selective fallback, 49 no match; expected-evidence hit 23.64%.
- Context: 100% retention when complete evidence was retrieved; 0 retrieved-but-dropped; one budget-exhausted case; no top-evidence-too-large case.
- Generation: 81.82% answer/citation presence/structural validity/expected-source match; 0 invalid and 0 parser-classified missing citations.
- Answerability: 10/10 correct unsupported-case abstentions, 0 unsupported direct answers; 10/55 answerable cases abstained, of which 2 had complete evidence and were attributed to `FALSE_ABSTENTION` after earlier-layer precedence.

Failure attribution: 55 PASS, 4 RETRIEVAL_MISS, 1 WRONG_DOCUMENT, 3 PARTIAL_MULTI_EVIDENCE_RETRIEVAL, 2 FALSE_ABSTENTION, and zero context/citation/unsupported-answer failures.

Evidence: `evaluation/reports/legal_eval_v2_baseline.json`, `.md`, and `legal_eval_v2_failure_analysis.md`.
