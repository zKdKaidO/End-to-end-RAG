# Legal Evaluation V2 Baseline

- Run status: **PASS**
- Dataset SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Cases: 65 (55 answerable, 10 unanswerable)
- Model / prompt: `qwen3.5:9b` / `legal-rag-v2`
- Thresholds enforced: **NO**

## Retrieval

| Metric | Result |
|---|---:|
| Hit@1 | 63.64% |
| Hit@3 | 74.55% |
| Hit@5 | 83.64% |
| Hit@10 | 85.45% |
| MRR | 0.7087 |
| Document Hit@1 | 96.36% |
| Document Hit@3 | 98.18% |
| Document Hit@5 | 98.18% |
| Document Hit@10 | 98.18% |
| Complete multi-evidence retrieval | 33.33% |
| Partial multi-evidence retrieval | 33.33% |
| Average required-evidence recall | 46.67% |

## Lexical contribution

- Non-empty rate: 24.62%
- Modes: `{"STRICT_MATCH": 0, "SELECTIVE_FALLBACK": 16, "NO_MATCH": 49}`
- Expected-evidence hit rate: 23.64%
- Expected-rank improved / harmed: 1 / 1

## Context

- Expected-evidence retention: 100.00%
- Retrieved but dropped: 0
- Budget exhausted: 1
- Top evidence exceeds budget: 0
- Average utilization: 50.87%

## Generation and answerability

- Answer produced: 81.82%
- Citation presence: 81.82%
- Citation structural validity: 81.82%
- Expected-source citation match: 81.82%
- Missing / invalid citation rate: 0.00% / 0.00%
- Correct abstention: 100.00%
- False abstention: 18.18%
- Unsupported direct answer: 0.00%

## Failure attribution

| Label | Count |
|---|---:|
| PASS | 55 |
| RETRIEVAL_MISS | 4 |
| WRONG_DOCUMENT | 1 |
| PARTIAL_MULTI_EVIDENCE_RETRIEVAL | 3 |
| CONTEXT_DROP | 0 |
| GENERATION_MISSING_CITATION | 0 |
| GENERATION_INVALID_CITATION | 0 |
| GENERATION_WRONG_SOURCE | 0 |
| FALSE_ABSTENTION | 2 |
| UNSUPPORTED_ANSWER | 0 |
| AMBIGUOUS | 0 |
| OTHER | 0 |

## Category breakdown

| Category | Cases | Hit@10 | Document Hit@10 | Citation match | Correct abstention |
|---|---:|---:|---:|---:|---:|
| DEEPER_RANK | 8 | 87.50% | 87.50% | 87.50% | N/A |
| DIRECT_FACT | 15 | 100.00% | 100.00% | 100.00% | N/A |
| DOCUMENT_DISAMBIGUATION | 3 | 100.00% | 100.00% | 66.67% | N/A |
| DOCUMENT_FILTER | 3 | 100.00% | 100.00% | 100.00% | N/A |
| HARD_UNANSWERABLE | 6 | N/A | N/A | N/A | 100.00% |
| KEYWORD_IDENTIFIER | 5 | 100.00% | 100.00% | 100.00% | N/A |
| MULTI_DOCUMENT_EVIDENCE | 1 | 100.00% | 100.00% | 100.00% | N/A |
| MULTI_EVIDENCE | 8 | 25.00% | 100.00% | 12.50% | N/A |
| NEAR_DUPLICATE_EVIDENCE | 1 | 100.00% | 100.00% | 100.00% | N/A |
| OUT_OF_CORPUS | 4 | N/A | N/A | N/A | 100.00% |
| PARTIAL_SUPPORT | 1 | 100.00% | 100.00% | 100.00% | N/A |
| SAME_ARTICLE_NUMBER | 3 | 100.00% | 100.00% | 100.00% | N/A |
| SAME_TERM_DIFFERENT_DOCUMENT | 2 | 50.00% | 100.00% | 50.00% | N/A |
| SEMANTIC_PARAPHRASE | 5 | 100.00% | 100.00% | 100.00% | N/A |

## Per-case results

| Case | Category | Retrieval | Context | Generation | Diagnosis | Total ms |
|---|---|---|---|---|---|---:|
| v2_social_scope | MULTI_EVIDENCE | NONE | NONE | INSUFFICIENT_EVIDENCE | RETRIEVAL_MISS | 21789.1 |
| v2_social_applicable_groups | MULTI_EVIDENCE | NONE | NONE | INSUFFICIENT_EVIDENCE | RETRIEVAL_MISS | 1391.6 |
| v2_social_practice_content | MULTI_EVIDENCE | PARTIAL | PARTIAL | INSUFFICIENT_EVIDENCE | PARTIAL_MULTI_EVIDENCE_RETRIEVAL | 1315.0 |
| v2_social_university_duration | SAME_ARTICLE_NUMBER | COMPLETE | COMPLETE | COMPLETED | PASS | 1827.9 |
| v2_social_college_duration | SEMANTIC_PARAPHRASE | COMPLETE | COMPLETE | COMPLETED | PASS | 3276.7 |
| v2_social_intermediate_duration | KEYWORD_IDENTIFIER | COMPLETE | COMPLETE | COMPLETED | PASS | 2571.2 |
| v2_social_training_sessions | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 2454.4 |
| v2_social_plan_deadline | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 1876.5 |
| v2_social_plan_submission_filter | DOCUMENT_FILTER | COMPLETE | COMPLETE | COMPLETED | PASS | 2290.3 |
| v2_social_multiple_instructors | SEMANTIC_PARAPHRASE | COMPLETE | COMPLETE | COMPLETED | PASS | 2417.1 |
| v2_social_program_review | DEEPER_RANK | COMPLETE | COMPLETE | COMPLETED | PASS | 2427.2 |
| v2_social_course_modes | SAME_TERM_DIFFERENT_DOCUMENT | NONE | NONE | INSUFFICIENT_EVIDENCE | RETRIEVAL_MISS | 1390.4 |
| v2_social_foreign_training | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 1645.9 |
| v2_social_research_credit | DEEPER_RANK | COMPLETE | COMPLETE | COMPLETED | PASS | 4272.0 |
| v2_social_thesis_update | KEYWORD_IDENTIFIER | COMPLETE | COMPLETE | COMPLETED | PASS | 2194.6 |
| v2_social_confidentiality | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 1915.9 |
| v2_social_confirmation_reporting | DEEPER_RANK | COMPLETE | COMPLETE | COMPLETED | PASS | 3164.6 |
| v2_social_effective_transition | MULTI_EVIDENCE | PARTIAL | PARTIAL | INSUFFICIENT_EVIDENCE | PARTIAL_MULTI_EVIDENCE_RETRIEVAL | 1421.4 |
| v2_bank_scope_ratios | MULTI_EVIDENCE | PARTIAL | PARTIAL | INSUFFICIENT_EVIDENCE | PARTIAL_MULTI_EVIDENCE_RETRIEVAL | 1209.9 |
| v2_bank_special_control_exception | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 2043.4 |
| v2_bank_actual_capital_formula | SEMANTIC_PARAPHRASE | COMPLETE | COMPLETE | COMPLETED | PASS | 1843.7 |
| v2_bank_low_capital_report | DEEPER_RANK | COMPLETE | COMPLETE | COMPLETED | PASS | 1832.4 |
| v2_bank_below_80_measures | PARTIAL_SUPPORT | COMPLETE | COMPLETE | COMPLETED | PASS | 3347.9 |
| v2_bank_min_capital_ratio_filter | DOCUMENT_FILTER | COMPLETE | COMPLETE | COMPLETED | PASS | 1578.6 |
| v2_bank_zero_risk_assets | KEYWORD_IDENTIFIER | COMPLETE | COMPLETE | COMPLETED | PASS | 1958.0 |
| v2_bank_fifty_risk_assets | SAME_ARTICLE_NUMBER | COMPLETE | COMPLETE | COMPLETED | PASS | 1880.7 |
| v2_bank_liquidity_100 | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 1840.7 |
| v2_bank_short_term_funding_30 | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 1586.5 |
| v2_bank_ratio_zero_condition | SEMANTIC_PARAPHRASE | COMPLETE | COMPLETE | COMPLETED | PASS | 1855.9 |
| v2_bank_deposit_multiple | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 1661.9 |
| v2_bank_board_loan_threshold | DEEPER_RANK | NONE | NONE | INSUFFICIENT_EVIDENCE | WRONG_DOCUMENT | 2046.6 |
| v2_bank_member_legal_entity_cap | DOCUMENT_DISAMBIGUATION | COMPLETE | COMPLETE | COMPLETED | PASS | 1719.7 |
| v2_bank_nonmember_cap | DOCUMENT_DISAMBIGUATION | COMPLETE | COMPLETE | COMPLETED | PASS | 1699.2 |
| v2_bank_loan_limit_exceptions | MULTI_EVIDENCE | NONE | NONE | INSUFFICIENT_EVIDENCE | RETRIEVAL_MISS | 1181.5 |
| v2_bank_risk_of_illiquidity | KEYWORD_IDENTIFIER | COMPLETE | COMPLETE | COMPLETED | PASS | 2432.6 |
| v2_bank_illiquidity_reporting | MULTI_EVIDENCE | COMPLETE | COMPLETE | COMPLETED | PASS | 2881.1 |
| v2_civil_scope | DOCUMENT_DISAMBIGUATION | COMPLETE | COMPLETE | INSUFFICIENT_EVIDENCE | FALSE_ABSTENTION | 2038.0 |
| v2_civil_training_nondiscrimination | SAME_ARTICLE_NUMBER | COMPLETE | COMPLETE | COMPLETED | PASS | 2333.4 |
| v2_civil_hard_area_commitment | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 2773.5 |
| v2_civil_priority_75 | KEYWORD_IDENTIFIER | COMPLETE | COMPLETE | COMPLETED | PASS | 2518.9 |
| v2_civil_priority_5 | NEAR_DUPLICATE_EVIDENCE | COMPLETE | COMPLETE | COMPLETED | PASS | 2284.9 |
| v2_civil_council_size | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 2052.9 |
| v2_civil_project_exam_time | DEEPER_RANK | COMPLETE | COMPLETE | COMPLETED | PASS | 2377.7 |
| v2_civil_exam_pass_score | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 2846.7 |
| v2_civil_application_window | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 2551.3 |
| v2_civil_result_notice | DEEPER_RANK | COMPLETE | COMPLETE | COMPLETED | PASS | 3151.9 |
| v2_civil_file_completion | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 2871.5 |
| v2_civil_start_work | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 2744.5 |
| v2_civil_secondment_duration | SEMANTIC_PARAPHRASE | COMPLETE | COMPLETE | COMPLETED | PASS | 2375.0 |
| v2_civil_appointment_term | SAME_TERM_DIFFERENT_DOCUMENT | COMPLETE | COMPLETE | COMPLETED | PASS | 2912.5 |
| v2_civil_rotation_duration | DEEPER_RANK | COMPLETE | COMPLETE | COMPLETED | PASS | 2247.4 |
| v2_civil_severance_half_month | DIRECT_FACT | COMPLETE | COMPLETE | COMPLETED | PASS | 2032.7 |
| v2_civil_retirement_notice_filter | DOCUMENT_FILTER | COMPLETE | COMPLETE | COMPLETED | PASS | 2774.9 |
| v2_civil_effect_and_repeal | MULTI_EVIDENCE | COMPLETE | COMPLETE | INSUFFICIENT_EVIDENCE | FALSE_ABSTENTION | 2112.3 |
| v2_cross_document_effective_dates | MULTI_DOCUMENT_EVIDENCE | COMPLETE | COMPLETE | COMPLETED | PASS | 2511.2 |
| v2_hard_social_practice_fee | HARD_UNANSWERABLE | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 1416.3 |
| v2_hard_social_online_practice | HARD_UNANSWERABLE | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 1535.2 |
| v2_hard_bank_statutory_capital | HARD_UNANSWERABLE | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 1298.4 |
| v2_hard_bank_administrative_fine | HARD_UNANSWERABLE | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 1247.8 |
| v2_hard_civil_exam_fee | HARD_UNANSWERABLE | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 1948.6 |
| v2_hard_civil_retirement_age | HARD_UNANSWERABLE | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 2260.1 |
| v2_out_personal_income_tax | OUT_OF_CORPUS | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 1501.9 |
| v2_out_offshore_wind_license | OUT_OF_CORPUS | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 1130.2 |
| v2_out_traffic_fine | OUT_OF_CORPUS | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 1207.3 |
| v2_out_private_maternity | OUT_OF_CORPUS | N/A | N/A | INSUFFICIENT_EVIDENCE | PASS | 1839.0 |

Raw candidates, scores, contexts, citations, provenance, and timings for every case are retained in the JSON artifact.
