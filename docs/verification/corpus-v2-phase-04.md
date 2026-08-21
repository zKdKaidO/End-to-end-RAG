# Corpus V2 Phase 04 — Evaluation V2 Dataset and Freeze

Date: 2026-08-19

Result: **PASS**.

- Dataset: `evaluation/datasets/legal_eval_v2.json`
- SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Cases: 65 total; 55 answerable; 10 unanswerable.
- Positive ground truth: 70 persisted `block3-v1` chunks across 3 real documents.
- Hard negatives: 6 topically close unsupported questions.
- Out-of-corpus controls: 4.

Strict validation passed for unique IDs, controlled categories, UUIDs, document/chunk existence, index version, content, provenance, source-reference containment, answerability contracts, and document filters.

Categories: `DIRECT_FACT` 15, `DEEPER_RANK` 8, `MULTI_EVIDENCE` 8, `HARD_UNANSWERABLE` 6, `KEYWORD_IDENTIFIER` 5, `SEMANTIC_PARAPHRASE` 5, `DOCUMENT_DISAMBIGUATION` 3, `DOCUMENT_FILTER` 3, `SAME_ARTICLE_NUMBER` 3, `SAME_TERM_DIFFERENT_DOCUMENT` 2, and one each of `MULTI_DOCUMENT_EVIDENCE`, `NEAR_DUPLICATE_EVIDENCE`, and `PARTIAL_SUPPORT`, plus 4 `OUT_OF_CORPUS`.

The dataset was frozen before execution and was not edited after observing failures. Evaluation V1 remains at its frozen SHA-256.

Human-review evidence: `evaluation/reports/legal_eval_v2_review.md` and `legal_eval_v2_dataset_freeze.md`.
