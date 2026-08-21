# Context Distraction Analysis V1

Ground truth is used here only for offline diagnosis. It is not used by any production-plausible ordering strategy.

| Case | Frozen false abstention | Context tokens | Selected | Support incl. anchors | Distractors | Before support tokens | After support tokens | Hierarchy children |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `v2_social_scope` | False | 1503 | 13 | 4 | 9 | 0 | 1306 | 3 |
| `v2_social_practice_content` | False | 1132 | 12 | 5 | 7 | 0 | 158 | 2 |
| `v2_social_university_duration` | False | 1083 | 10 | 1 | 9 | 336 | 680 | 0 |
| `v2_social_college_duration` | False | 1719 | 12 | 1 | 11 | 0 | 1657 | 2 |
| `v2_social_intermediate_duration` | False | 3585 | 10 | 1 | 9 | 0 | 3524 | 0 |
| `v2_social_training_sessions` | False | 3320 | 10 | 1 | 9 | 0 | 3139 | 0 |
| `v2_social_plan_deadline` | False | 1391 | 10 | 1 | 9 | 0 | 1320 | 0 |
| `v2_social_plan_submission_filter` | False | 2116 | 10 | 1 | 9 | 0 | 1995 | 0 |
| `v2_social_multiple_instructors` | False | 3626 | 14 | 1 | 13 | 0 | 3472 | 4 |
| `v2_social_program_review` | False | 1934 | 15 | 1 | 14 | 0 | 1850 | 5 |
| `v2_social_course_modes` | False | 2258 | 20 | 2 | 18 | 232 | 1931 | 10 |
| `v2_social_foreign_training` | False | 1798 | 17 | 1 | 16 | 273 | 1466 | 7 |
| `v2_social_research_credit` | False | 1551 | 18 | 1 | 17 | 1252 | 129 | 8 |
| `v2_social_thesis_update` | False | 1604 | 15 | 1 | 14 | 0 | 1533 | 5 |
| `v2_social_confidentiality` | False | 1374 | 10 | 1 | 9 | 0 | 1306 | 0 |
| `v2_social_confirmation_reporting` | False | 2719 | 12 | 1 | 11 | 0 | 2494 | 2 |
| `v2_bank_scope_ratios` | True | 1750 | 21 | 6 | 15 | 346 | 868 | 11 |
| `v2_bank_special_control_exception` | False | 1227 | 12 | 1 | 11 | 0 | 1132 | 2 |
| `v2_bank_low_capital_report` | False | 1299 | 12 | 1 | 11 | 0 | 1096 | 2 |
| `v2_bank_below_80_measures` | True | 1399 | 13 | 1 | 12 | 251 | 896 | 3 |
| `v2_bank_min_capital_ratio_filter` | False | 1374 | 14 | 1 | 13 | 346 | 979 | 4 |
| `v2_bank_zero_risk_assets` | False | 1881 | 10 | 1 | 9 | 641 | 1092 | 0 |
| `v2_bank_fifty_risk_assets` | False | 1625 | 11 | 1 | 10 | 0 | 1538 | 1 |
| `v2_bank_liquidity_100` | False | 1243 | 10 | 1 | 9 | 0 | 1154 | 0 |
| `v2_bank_short_term_funding_30` | False | 1411 | 15 | 1 | 14 | 274 | 1072 | 5 |
| `v2_bank_ratio_zero_condition` | False | 1411 | 15 | 1 | 14 | 0 | 1300 | 5 |
| `v2_bank_deposit_multiple` | False | 1215 | 10 | 1 | 9 | 0 | 1152 | 0 |
| `v2_bank_board_loan_threshold` | False | 1759 | 13 | 1 | 12 | 0 | 1628 | 3 |
| `v2_bank_member_legal_entity_cap` | False | 873 | 12 | 1 | 11 | 0 | 797 | 2 |
| `v2_bank_nonmember_cap` | False | 1224 | 13 | 1 | 12 | 0 | 1149 | 3 |
| `v2_bank_loan_limit_exceptions` | False | 2708 | 22 | 3 | 19 | 73 | 2464 | 12 |
| `v2_bank_risk_of_illiquidity` | False | 1159 | 11 | 1 | 10 | 0 | 1035 | 1 |
| `v2_bank_illiquidity_reporting` | False | 983 | 10 | 2 | 8 | 0 | 580 | 0 |
| `v2_civil_scope` | True | 4049 | 17 | 1 | 16 | 0 | 3482 | 7 |
| `v2_civil_training_nondiscrimination` | False | 3934 | 12 | 1 | 11 | 0 | 3592 | 5 |
| `v2_civil_hard_area_commitment` | False | 3792 | 10 | 1 | 9 | 0 | 3546 | 0 |
| `v2_civil_priority_75` | False | 3903 | 12 | 1 | 11 | 0 | 3638 | 3 |
| `v2_civil_priority_5` | False | 2946 | 10 | 1 | 9 | 0 | 2409 | 0 |
| `v2_civil_council_size` | False | 3966 | 15 | 1 | 14 | 0 | 3703 | 8 |
| `v2_civil_project_exam_time` | False | 3897 | 11 | 1 | 10 | 0 | 3548 | 2 |
| `v2_civil_exam_pass_score` | False | 3832 | 12 | 1 | 11 | 596 | 2954 | 4 |
| `v2_civil_application_window` | False | 3947 | 13 | 1 | 12 | 0 | 3686 | 4 |
| `v2_civil_result_notice` | False | 3658 | 11 | 1 | 10 | 0 | 3339 | 2 |
| `v2_civil_file_completion` | False | 3955 | 11 | 1 | 10 | 0 | 3670 | 4 |
| `v2_civil_start_work` | False | 3829 | 13 | 1 | 12 | 0 | 3558 | 4 |
| `v2_civil_secondment_duration` | False | 3782 | 13 | 1 | 12 | 0 | 3359 | 6 |
| `v2_civil_appointment_term` | False | 3587 | 10 | 1 | 9 | 0 | 3318 | 0 |
| `v2_civil_rotation_duration` | False | 3187 | 10 | 1 | 9 | 752 | 2175 | 0 |
| `v2_civil_severance_half_month` | False | 3995 | 15 | 1 | 14 | 588 | 3122 | 6 |
| `v2_civil_retirement_notice_filter` | False | 3433 | 10 | 1 | 9 | 0 | 3145 | 0 |
| `v2_civil_effect_and_repeal` | False | 2424 | 10 | 2 | 8 | 364 | 54 | 0 |
| `v2_cross_document_effective_dates` | True | 1545 | 11 | 2 | 9 | 133 | 1222 | 1 |


## Descriptive correlations

```json
{
  "context_tokens_vs_false_abstention": -0.05632409918204759,
  "distractor_count_vs_false_abstention": 0.18046128784211687,
  "hierarchy_child_count_vs_false_abstention": 0.23293218918414865
}
```

Context-size buckets: `{"LOW": {"case_count": 18, "token_range": [873, 1545], "frozen_false_abstention_rate": 0.1111111111111111}, "MEDIUM": {"case_count": 17, "token_range": [1551, 3320], "frozen_false_abstention_rate": 0.058823529411764705}, "HIGH": {"case_count": 17, "token_range": [3433, 4049], "frozen_false_abstention_rate": 0.058823529411764705}}`.

Hierarchy-child comparison: `{"NO_HIERARCHY_CHILD": {"case_count": 16, "frozen_false_abstention_rate": 0.0, "mean_context_tokens": 2347.5}, "HAS_HIERARCHY_CHILD": {"case_count": 36, "frozen_false_abstention_rate": 0.1111111111111111, "mean_context_tokens": 2426.527777777778}}`.

These are small-sample correlations, not causal proof. Similar-length successful controls recorded in the JSON show that length alone is not a sufficient explanation.
