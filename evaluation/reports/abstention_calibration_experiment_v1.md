# Supported-Case Abstention Calibration Experiment V1

Status: **MORE_DIAGNOSIS_REQUIRED**

## Frozen state

- Evaluation V1: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Production prompt: `legal-rag-v2` — unchanged
- Production model: `qwen3.5:9b` — unchanged
- Retrieval, hierarchy retrieval, Block 5, parser semantics, streaming protocol, and schema: unchanged

## Baseline repeatability

- Complete-context false-abstention cases: 4 (v2_bank_scope_ratios, v2_bank_below_80_measures, v2_civil_scope, v2_cross_document_effective_dates).
- Current-prompt false-case repeats: ANSWERABLE 3, INSUFFICIENT 9.
- Successful answerable control stability: 100.00%.
- Unanswerable repeat stability: 100.00%; unsupported direct answers 0.
- Stable false abstentions: 3 (v2_bank_scope_ratios, v2_bank_below_80_measures, v2_civil_scope).
- Historical false abstention not reproduced: 1 (v2_cross_document_effective_dates).

## Support modes

- `COMPOSITIONAL`: 1
- `CONDITIONAL`: 1
- `DIRECT_MULTI`: 1
- `DIRECT_SINGLE`: 1

## Variant comparison

| Variant | False-case ANSWERABLE | Grounded conversion | Unanswerable abstention | Unsupported |
|---|---:|---:|---:|---:|
| variant-a | 75.00% | 50.00% | 100.00% | 0 |
| variant-b | 75.00% | 50.00% | 100.00% | 0 |
| fewshot | 75.00% | 50.00% | 100.00% | 0 |
| combined | 75.00% | 50.00% | 100.00% | 0 |

Best diagnostic variant: **combined**. Production-eligible variant: **none**.

## Full 55-answerable fixed-context run

- Answerable accepted: 90.91%.
- False abstention: 7.27%.
- Citation structural validity: 87.27%.
- Expected-source match: 85.45%.
- Status-format failures: 1.
- Initial A/B/few-shot citation validity: 74.55% / 72.73% / 12.73%.
- The combined variant restored aggregate citation validity and expected-source match to baseline, but emitted a duplicate status marker in one full-corpus case and therefore failed the structured-status rule.

## Evidence presentation ablations

- Current-order ANSWERABLE rate: 25.00%.
- Evidence-first ANSWERABLE rate: 50.00%.
- Grouped-support ANSWERABLE rate: 25.00%.
- Material order effect: **YES**.
- Minimal evidence with current prompt: 50.00%.
- Minimal evidence with best prompt: 75.00%.
- Context distraction supported: **YES**.

## Root-cause observations

- Prompt over-conservatism: supported for the two bank cases.
- Context distraction: supported for `v2_civil_scope` (minimal combined 3/3; full combined 0/3).
- Evidence ordering: material and case-specific; evidence-first fixed the two bank cases 3/3, while grouped support did not improve the aggregate.
- Multi-evidence synthesis: a real factor for `v2_bank_scope_ratios`.
- Hierarchy-child correlation: weak descriptive signal, not a causal result.
- Model capacity: not dominant; the same 9B model answered three diagnostic cases under controlled conditions.
- Ground-truth ambiguity: none excluded; parent-anchor context is necessary when interpreting hierarchy child bullets.

## Prompt size and latency

- Combined system-prompt token delta: +38.
- TTFT baseline/combined: 1783.9 / 1786.8 ms.
- Generation baseline/combined: 2562.9 / 3366.9 ms.

## Recommendation

Recommended next production target: **NO CHANGE** (confidence: MEDIUM).

Selected only after targeted repeats, all ten unanswerable safety controls, and a full 55-answerable fixed-context run.

No production calibration was implemented. Expected-source matching is not semantic entailment; full evidence/answer review packages remain available for human review.

## Remaining complete-context false abstentions

- `v2_civil_scope`: `CONTEXT_DISTRACTION`
