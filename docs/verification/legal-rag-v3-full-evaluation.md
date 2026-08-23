# Legal-RAG-V3 Same-Run Full Evaluation

Date: 2026-08-22

Method: 55 frozen answerable V2 cases for each prompt, identical frozen current-index retrieval snapshots, P0 context, model, tokenizer, provider, and generation settings. Calls were interleaved per case as V2 then V3.

| Metric | V2 | V3 | Delta |
|---|---:|---:|---:|
| Answerable acceptance | 49/55 (89.09%) | 52/55 (94.55%) | +3 cases / +5.45 pp |
| False abstention | 6/55 (10.91%) | 3/55 (5.45%) | -3 cases / -5.45 pp |
| Citation presence | 89.09% | 94.55% | +5.45 pp |
| Citation structural validity | 89.09% | 94.55% | +5.45 pp |
| Expected-source match | 48/55 (87.27%) | 49/55 (89.09%) | +1 case / +1.82 pp |
| Status validity | 100% | 100% | unchanged |
| Missing citation | 0% | 0% | unchanged |
| Invalid citation | 0% | 0% | unchanged |

Paired acceptance gains: `v2_bank_below_80_measures`, `v2_bank_scope_ratios`, `v2_social_effective_transition`. Paired acceptance losses: none. Paired expected-source gains: three; losses: `v2_social_plan_submission_filter` and `v2_social_practice_content`; net +1. Those substitutions are queued for human review, not semantically adjudicated.

## Breakdown

| Class | Cases | V2 grounded | V3 grounded | V2 false abstention | V3 false abstention |
|---|---:|---:|---:|---:|---:|
| Single evidence | 46 | 91.30% | 93.48% | 6.52% | 4.35% |
| Multi evidence | 9 | 66.67% | 66.67% | 33.33% | 11.11% |
| Hierarchy recovered | 5 | 80.00% | 80.00% | 20.00% | 0.00% |
| Multi-document | 1 | 100% | 100% | 0% | 0% |
| Qualified/partial support | 1 | 0/1 | 1/1 | 1/1 | 0/1 |

Multi-evidence answerability improved, but grounded/expected-source performance remains 66.67%; this weakness is not hidden by the aggregate.
