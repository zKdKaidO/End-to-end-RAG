# Abstention Context Position Analysis V1

Token positions are approximate chat-template positions measured by the real production tokenizer. Source positions are exact.

| Case | Outcome | Sources | Required S positions | Approx token positions | Utilization | Hierarchy support |
|---|---|---:|---|---|---:|---|
| v2_bank_scope_ratios | FALSE_ABSTENTION | 21 | [9, 3, 4, 5, 6] | [1271, 840, 881, 933, 975] | 42.72% | yes |
| v2_bank_below_80_measures | FALSE_ABSTENTION | 13 | [4] | [681] | 34.16% | no |
| v2_civil_scope | FALSE_ABSTENTION | 17 | [1] | [421] | 98.85% | no |
| v2_cross_document_effective_dates | FALSE_ABSTENTION | 11 | [5, 2] | [709, 569] | 37.72% | no |
| v2_social_scope | PASS | 13 | [2, 3, 4] | [497, 538, 576] | 36.69% | yes |
| v2_social_practice_content | PASS | 12 | [3, 4, 11, 1] | [563, 605, 1357, 415] | 27.64% | yes |
| v2_social_university_duration | PASS | 10 | [4] | [765] | 26.44% | no |
| v2_social_college_duration | PASS | 12 | [1] | [417] | 41.97% | no |
| v2_social_intermediate_duration | PASS | 10 | [1] | [419] | 87.52% | no |
| v2_social_training_sessions | PASS | 10 | [1] | [418] | 81.05% | no |
| v2_social_plan_deadline | PASS | 10 | [1] | [415] | 33.96% | no |
| v2_social_plan_submission_filter | PASS | 10 | [1] | [426] | 51.66% | no |
| v2_social_multiple_instructors | PASS | 14 | [1] | [418] | 88.53% | no |
| v2_social_program_review | PASS | 15 | [1] | [422] | 47.22% | no |
| v2_social_course_modes | PASS | 20 | [4] | [703] | 55.13% | yes |
| v2_social_foreign_training | PASS | 17 | [2] | [692] | 43.90% | no |
| v2_social_research_credit | PASS | 18 | [17] | [1674] | 37.87% | no |
| v2_social_thesis_update | PASS | 15 | [1] | [421] | 39.16% | no |
| v2_social_confidentiality | PASS | 10 | [1] | [416] | 33.54% | no |
| v2_social_confirmation_reporting | PASS | 12 | [1] | [426] | 66.38% | no |
| v2_bank_special_control_exception | PASS | 12 | [1] | [438] | 29.96% | no |
| v2_bank_low_capital_report | PASS | 12 | [1] | [426] | 31.71% | no |
| v2_bank_min_capital_ratio_filter | PASS | 14 | [2] | [778] | 33.54% | no |
| v2_bank_zero_risk_assets | PASS | 10 | [2] | [1062] | 45.92% | no |
| v2_bank_fifty_risk_assets | PASS | 11 | [1] | [430] | 39.67% | no |
| v2_bank_liquidity_100 | PASS | 10 | [1] | [428] | 30.35% | no |
| v2_bank_short_term_funding_30 | PASS | 15 | [4] | [691] | 34.45% | no |
| v2_bank_ratio_zero_condition | PASS | 15 | [1] | [426] | 34.45% | no |
| v2_bank_deposit_multiple | PASS | 10 | [1] | [419] | 29.66% | no |
| v2_bank_board_loan_threshold | PASS | 13 | [1] | [423] | 42.94% | no |
| v2_bank_member_legal_entity_cap | PASS | 12 | [1] | [425] | 21.31% | no |
| v2_bank_nonmember_cap | PASS | 13 | [1] | [414] | 29.88% | no |
| v2_bank_loan_limit_exceptions | PASS | 22 | [3, 4] | [545, 609] | 66.11% | yes |
| v2_bank_risk_of_illiquidity | PASS | 11 | [1] | [420] | 28.30% | no |
| v2_bank_illiquidity_reporting | PASS | 10 | [4, 1] | [758, 422] | 24.00% | no |
| v2_civil_training_nondiscrimination | PASS | 12 | [1] | [421] | 96.04% | no |
| v2_civil_hard_area_commitment | PASS | 10 | [1] | [423] | 92.58% | no |
| v2_civil_priority_75 | PASS | 12 | [1] | [420] | 95.29% | no |
| v2_civil_priority_5 | PASS | 10 | [1] | [420] | 71.92% | no |
| v2_civil_council_size | PASS | 15 | [1] | [409] | 96.83% | no |
| v2_civil_project_exam_time | PASS | 11 | [1] | [417] | 95.14% | no |
| v2_civil_exam_pass_score | PASS | 12 | [2] | [1012] | 93.55% | no |
| v2_civil_application_window | PASS | 13 | [1] | [412] | 96.36% | no |
| v2_civil_result_notice | PASS | 11 | [1] | [424] | 89.31% | no |
| v2_civil_file_completion | PASS | 11 | [1] | [417] | 96.56% | no |
| v2_civil_start_work | PASS | 13 | [1] | [417] | 93.48% | no |
| v2_civil_secondment_duration | PASS | 13 | [1] | [410] | 92.33% | no |
| v2_civil_appointment_term | PASS | 10 | [1] | [417] | 87.57% | no |
| v2_civil_rotation_duration | PASS | 10 | [3] | [1164] | 77.81% | no |
| v2_civil_severance_half_month | PASS | 15 | [3] | [1007] | 97.53% | no |
| v2_civil_retirement_notice_filter | PASS | 10 | [1] | [421] | 83.81% | no |
| v2_civil_effect_and_repeal | PASS | 10 | [5, 9] | [805, 2215] | 59.18% | no |

## Group comparison

- Mean first relevant source, false/pass: 2.50 / 1.83.
- Mean last relevant source, false/pass: 4.75 / 2.25.
- Mean context tokens, false/pass: 2185.75 / 2420.25.
- Required hierarchy evidence, false/pass: 25.00% / 8.33%.

Position, length, and hierarchy origin are descriptive correlates only. The ordering and minimal-evidence ablations provide the controlled evidence about presentation effects.
