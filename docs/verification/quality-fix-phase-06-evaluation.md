# Quality Fix Phase 06 — Frozen 32-Case Evaluation

Date: 2026-08-19

Dataset SHA-256 before and after evaluation:

`afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`

Dataset changed: NO.

## Before / after

| Metric | Before | After |
|---|---:|---:|
| Hit@1 | 85.19% | 85.19% |
| Hit@3 | 92.59% | 92.59% |
| Hit@5 | 92.59% | 92.59% |
| Hit@10 | 92.59% | 92.59% |
| MRR | 88.89% | 88.89% |
| Lexical non-empty | 0.00% | 18.75% |
| Lexical expected solution | 0.00% | 22.22% |
| Context evidence retention | 100.00% | 100.00% |
| Citation presence | 88.89% | 96.30% |
| Citation structural validity | 88.89% | 100.00% |
| Expected-source citation match | 81.48% | 85.19% |
| Invalid citation rate | 0.00% | 0.00% |
| Missing citation rate | 11.11% | 0.00% |
| Correct machine abstention | 0.00% | 100.00% |
| Unsupported direct-answer rate | 100.00% | 0.00% |

## Latency means

| Stage | Before ms | After ms |
|---|---:|---:|
| Retrieval | 41.99 | 47.01 |
| Context | 18.42 | 17.24 |
| TTFT | 608.42 | 1,080.36 |
| Generation | 3,084.57 | 2,137.26 |
| Total | 3,401.81 | 2,448.50 |

One answerable case (`ministry_approves_list`) safely abstained after the fix: the selected action chunk omits the responsible authority, while the separate Điều 9 responsibility heading was not present in final context. This measured false negative is retained and documented; neither the frozen dataset nor out-of-scope retrieval/context contracts were changed.

Reports:

- `evaluation/reports/legal_eval_v1_after_quality_fixes.md`
- `evaluation/reports/legal_eval_v1_after_quality_fixes.json`
- `evaluation/reports/quality_fix_before_after_v1.md`
- `evaluation/reports/quality_fix_before_after_v1.json`

Result: PASS with disclosed limitations.
