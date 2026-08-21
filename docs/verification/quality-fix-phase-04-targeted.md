# Quality Fix Phase 04 — Real Targeted Regression

Date: 2026-08-19

Runtime: real Block 4, real Block 5, real Block 6, production `legal-rag-v2` profile, real `qwen3.5:9b`.

## Frozen unanswerable cases

- Cases executed: 5/5
- Authoritative `INSUFFICIENT_EVIDENCE` markers: 5/5
- Public `INSUFFICIENT_EVIDENCE`: 5/5
- Unsupported direct answers: 0/5
- Citations and invalid citations: empty for all five
- Provider calls: exactly one per case
- Public marker exposure: none

## Historical citation failures

- `nsmo_definition`: valid `[S1]` in 3/3 real runs
- `domestic_expert_pay_cap`: valid `[S1]` in 3/3 real runs
- Stability total: 6/6

## Multi-evidence recheck

- `applicable_entities_multi`: two required chunks remain absent from both candidate pools; the third remains dense/final rank 5.
- `national_dispatcher_role`: one required chunk remains dense/final rank 1; the second remains dense rank 13 and outside final Top 10.
- Top-K, dense retrieval, RRF, and reranking were not changed.

## Wrong-source recheck

The existing case remains `PLAUSIBLE_ALTERNATIVE_EVIDENCE` pending explicit human legal review. Ground truth was not modified.

Detailed evidence: `evaluation/reports/quality_fix_targeted_v1.json`.

Result: PASS for the approved targeted criteria.
