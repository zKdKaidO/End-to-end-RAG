# Legal-RAG-V3 Targeted Grounding Amendment Experiment V1

Decision: **NONE — TARGETED PROMPT AMENDMENT NOT SUFFICIENT**

## Integrity and isolation

- Evaluation V1: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- legal-rag-v2: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- legal-rag-v3/E0: `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf`
- Production default after experiment: `legal-rag-v2`
- Production files/prompts changed by experiment: **NO**

## Variants

| Variant | Policy | SHA-256 | System tokens | Delta vs E0 |
|---|---|---|---:|---:|
| E0 | BASELINE | `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf` | 320 | 0 |
| E1 | WHOLE-QUESTION SUFFICIENCY | `ae7d35a85fdd5db661ed43b198c9dc67c6c6e2513b5a8b3989f83c963bd83da2` | 491 | 171 |
| E2 | BOUNDED QUALIFIED RESPONSE | `353c0aa1749be65b16eba59fa0708b0bc2c8cee4fbeeabd2dfcae5b3fc668e5f` | 521 | 201 |

No additional few-shot was used.

## Targeted repeated runs

### v2_bank_below_80_measures

| Variant | Answerable | Insufficient | Grounded engineering pass | Classifications |
|---|---:|---:|---:|---|
| E0 | 5/5 | 0/5 | 0/5 | `{"FAIL_SCOPE_AND_CITATION_ALIGNMENT": 5}` |
| E1 | 0/5 | 5/5 | 0/5 | `{"FAIL_FALSE_ABSTENTION": 5}` |
| E2 | 5/5 | 0/5 | 0/5 | `{"FAIL_SCOPE_AND_CITATION_ALIGNMENT": 5}` |

### v2_social_effective_transition

| Variant | Answerable | Insufficient | Grounded engineering pass | Classifications |
|---|---:|---:|---:|---|
| E0 | 5/5 | 0/5 | 0/5 | `{"FAIL_UNSUPPORTED_DATE": 5}` |
| E1 | 0/5 | 5/5 | 5/5 | `{"PASS_SAFE_PARTIAL_COVERAGE": 5}` |
| E2 | 0/5 | 5/5 | 0/5 | `{"FAIL_INSUFFICIENT_CONTINUATION": 5}` |

### v2_social_plan_submission_filter

| Variant | Answerable | Insufficient | Grounded engineering pass | Classifications |
|---|---:|---:|---:|---|
| E0 | 5/5 | 0/5 | 0/5 | `{"FAIL_ACTION_SUBSTITUTION": 5}` |
| E1 | 5/5 | 0/5 | 5/5 | `{"PASS": 5}` |
| E2 | 5/5 | 0/5 | 0/5 | `{"FAIL_ACTION_SUBSTITUTION": 5}` |

### v2_social_practice_content

| Variant | Answerable | Insufficient | Grounded engineering pass | Classifications |
|---|---:|---:|---:|---|
| E0 | 5/5 | 0/5 | 0/5 | `{"FAIL_CITATION_ALIGNMENT": 5}` |
| E1 | 5/5 | 0/5 | 0/5 | `{"FAIL_CITATION_ALIGNMENT": 5}` |
| E2 | 5/5 | 0/5 | 0/5 | `{"FAIL_CITATION_ALIGNMENT": 5}` |

### v2_bank_scope_ratios

| Variant | Answerable | Insufficient | Grounded engineering pass | Classifications |
|---|---:|---:|---:|---|
| E0 | 5/5 | 0/5 | 5/5 | `{"PASS": 5}` |
| E1 | 0/5 | 5/5 | 0/5 | `{"FAIL_POSITIVE_CONTROL_ABSTENTION": 5}` |
| E2 | 0/5 | 5/5 | 0/5 | `{"FAIL_INSUFFICIENT_CONTINUATION": 5}` |

## Failure-class metrics

| Variant | Unsupported proposition | Wrong action | Unsupported date | Claim citation aligned | Scope widened | Harmful superfluousness | Grounded |
|---|---:|---:|---:|---:|---:|---:|---:|
| E0 | 15/25 | 5/25 | 5/25 | 50/60 (+5 unclear) | 5/25 | 5/25 | 5/25 |
| E1 | 0/25 | 0/25 | 0/25 | 50/55 (+0 unclear) | 0/25 | 0/25 | 10/25 |
| E2 | 10/25 | 5/25 | 0/25 | 55/70 (+0 unclear) | 5/25 | 5/25 | 0/25 |

## Full 55-case answerable regression

| Variant | Acceptance | False abstention | Citation validity | Expected source | Status validity |
|---|---:|---:|---:|---:|---:|
| E0 | 94.55% | 5.45% | 94.55% | 89.09% | 100.00% |
| E1 | 85.45% | 14.55% | 85.45% | 85.45% | 100.00% |
| E2 | 89.09% | 10.91% | 89.09% | 87.27% | 100.00% |

## Multi-evidence breakdown

### single_evidence

| Variant | Runs | Accepted | Grounded expected-source | False abstention | Citation validity |
|---|---:|---:|---:|---:|---:|
| E0 | 46 | 95.65% | 93.48% | 4.35% | 95.65% |
| E1 | 46 | 91.30% | 91.30% | 8.70% | 91.30% |
| E2 | 46 | 95.65% | 93.48% | 4.35% | 95.65% |

### multi_evidence

| Variant | Runs | Accepted | Grounded expected-source | False abstention | Citation validity |
|---|---:|---:|---:|---:|---:|
| E0 | 9 | 88.89% | 66.67% | 11.11% | 88.89% |
| E1 | 9 | 55.56% | 55.56% | 44.44% | 55.56% |
| E2 | 9 | 55.56% | 55.56% | 44.44% | 55.56% |

### hierarchy_recovered

| Variant | Runs | Accepted | Grounded expected-source | False abstention | Citation validity |
|---|---:|---:|---:|---:|---:|
| E0 | 5 | 100.00% | 80.00% | 0.00% | 100.00% |
| E1 | 5 | 80.00% | 80.00% | 20.00% | 80.00% |
| E2 | 5 | 80.00% | 80.00% | 20.00% | 80.00% |

### multi_document

| Variant | Runs | Accepted | Grounded expected-source | False abstention | Citation validity |
|---|---:|---:|---:|---:|---:|
| E0 | 1 | 100.00% | 100.00% | 0.00% | 100.00% |
| E1 | 1 | 100.00% | 100.00% | 0.00% | 100.00% |
| E2 | 1 | 100.00% | 100.00% | 0.00% | 100.00% |

### partial_qualified

| Variant | Runs | Accepted | Grounded expected-source | False abstention | Citation validity |
|---|---:|---:|---:|---:|---:|
| E0 | 1 | 100.00% | 100.00% | 0.00% | 100.00% |
| E1 | 1 | 0.00% | 0.00% | 100.00% | 0.00% |
| E2 | 1 | 100.00% | 100.00% | 0.00% | 100.00% |

## Synthetic diagnostics

Benchmark leakage: **NONE**

| Set | E0 | E1 | E2 |
|---|---:|---:|---:|
| partial_coverage | 6/6 | 6/6 | 1/6 |
| action_disambiguation | 5/6 | 5/6 | 5/6 |
| citation_alignment | 6/6 | 5/6 | 6/6 |

## Repeated safety

- Finalists: **NONE**. Both candidates failed the targeted positive-control/answerability-preservation gate, so the finalist-only safety stage was not reached (0 runs required under the declared procedure).

## Tokens and latency

| Variant | Model-facing tokens mean/p95/max | TTFT mean | Generation mean |
|---|---:|---:|---:|
| E0 | 2178.0 / 4338.6 / 4452 | 822.4 ms | 1957.1 ms |
| E1 | 2349.0 / 4509.6 / 4623 | 756.7 ms | 1563.3 ms |
| E2 | 2379.0 / 4539.6 / 4653 | 773.6 ms | 2080.7 ms |

Latency is observational and not an SLA.

## Root cause and upstream separation

- Prompt-contract weakness supported: **YES**
- Model capacity proven root cause: **NO**
- Model capacity may contribute: **YES**
- Future model-capacity ablation justified: **YES**
- Effective-transition correct date cannot be recovered by Block 6 because its source is absent; only unsafe invention is counted against Block 6.
- `v2_bank_actual_capital_formula` and `v2_social_applicable_groups` remain upstream evidence-availability failures.

Full-corpus semantic unsupported-answer counts are not claimed without human review; deterministic failure-class auditing is limited to the targeted cases and synthetic controls.

## Decision

Neither candidate cleared every deterministic targeted, answerability-preservation, and repeated-safety gate.

No production prompt was modified or activated.

## Regression

- Backend: 245 collected, 245 passed, 0 failed, 8 warnings, 90.31 seconds.
- Frontend: 5 files and 11 tests passed, 0 failed, 1.32 seconds.
- Production frontend build: PASS; 30 modules transformed in 166 ms.
