# Multi-Evidence Context Simulation V1

Real frozen Block 5 and production tokenizer/config were used offline.

| Strategy | Avg input | Avg selected | Avg tokens | Utilization | Exhausted | Multi complete | Retrieved→dropped |
|---|---:|---:|---:|---:|---:|---:|---:|
| BASELINE_TOP10 | 10.00 | 9.98 | 2096.2 | 51.18% | 0 | 33.33% | 0 |
| WIDER_RRF_TOP15 | 15.00 | 13.91 | 2733.5 | 66.74% | 20 | 33.33% | 0 |
| WIDER_RRF_TOP20 | 20.00 | 16.85 | 3165.4 | 77.28% | 23 | 33.33% | 0 |
| WIDER_RRF_TOP30 | 29.96 | 21.69 | 3733.9 | 91.16% | 34 | 33.33% | 0 |
| WIDER_RRF_TOP50 | 38.78 | 23.44 | 3919.4 | 95.69% | 50 | 33.33% | 0 |
| H1_PARENT | 15.98 | 14.62 | 2538.7 | 61.98% | 19 | 33.33% | 0 |
| H2_CHILDREN | 13.36 | 12.64 | 2416.7 | 59.00% | 11 | 66.67% | 0 |
| H3_SIBLINGS | 26.33 | 20.24 | 3153.9 | 77.00% | 24 | 55.56% | 1 |
| H4_SAME_ARTICLE | 25.96 | 19.42 | 2994.3 | 73.10% | 22 | 44.44% | 1 |
| H5_ADJACENT_UNIT | 23.82 | 19.15 | 3030.0 | 73.98% | 23 | 55.56% | 0 |
| H6_PARENT_CHILDREN | 18.82 | 16.33 | 2674.5 | 65.30% | 21 | 66.67% | 0 |
| H7_ARTICLE_ADJACENT | 27.91 | 20.84 | 3122.1 | 76.22% | 24 | 55.56% | 1 |
| COVERAGE_AWARE_TOP10 | 10.00 | 9.98 | 2084.8 | 50.90% | 0 | 33.33% | 0 |
| H7_PLUS_WIDER15 | 37.09 | 25.91 | 3643.9 | 88.96% | 34 | 55.56% | 1 |

## Grouped legal-unit diagnostic

Average tokens before/after: 1922.6 / 1768.6.
Average token savings: 154.0.
This is a temporary token diagnostic, not a Block 5 proposal or persisted representation.