# Multi-Evidence Strategy Comparison V1

All strategies are offline replays. No production parameter was changed.

| Strategy | Candidates | Hit@10 | MRR | Multi complete@10 | Multi recall@10 | Context complete | Budget exhausted |
|---|---:|---:|---:|---:|---:|---:|---:|
| BASELINE_TOP10 | 10.0 | 85.45% | 0.7087 | 33.33% | 46.67% | 33.33% | 0 |
| WIDER_RRF_TOP15 | 15.0 | 85.45% | 0.7087 | 33.33% | 46.67% | 33.33% | 20 |
| WIDER_RRF_TOP20 | 20.0 | 85.45% | 0.7087 | 33.33% | 46.67% | 33.33% | 23 |
| WIDER_RRF_TOP30 | 30.0 | 85.45% | 0.7087 | 33.33% | 46.67% | 33.33% | 34 |
| WIDER_RRF_TOP50 | 38.8 | 85.45% | 0.7087 | 33.33% | 46.67% | 33.33% | 50 |
| H1_PARENT | 16.0 | 83.64% | 0.6895 | 33.33% | 43.89% | 33.33% | 19 |
| H2_CHILDREN | 13.4 | 92.73% | 0.7217 | 66.67% | 81.11% | 66.67% | 11 |
| H3_SIBLINGS | 26.3 | 85.45% | 0.7145 | 44.44% | 56.67% | 55.56% | 24 |
| H4_SAME_ARTICLE | 26.0 | 83.64% | 0.6931 | 33.33% | 52.78% | 44.44% | 22 |
| H5_ADJACENT_UNIT | 23.8 | 87.27% | 0.6987 | 33.33% | 58.70% | 55.56% | 23 |
| H6_PARENT_CHILDREN | 18.8 | 92.73% | 0.7035 | 66.67% | 78.89% | 66.67% | 21 |
| H7_ARTICLE_ADJACENT | 27.9 | 85.45% | 0.6889 | 44.44% | 58.33% | 55.56% | 24 |
| COVERAGE_AWARE_TOP10 | 10.0 | 85.45% | 0.7087 | 33.33% | 46.67% | 33.33% | 0 |
| H7_PLUS_WIDER15 | 37.1 | 85.45% | 0.6889 | 44.44% | 58.33% | 55.56% | 34 |

Best measured strategy: **H2_CHILDREN**.
Reranker tested: **NONE**.
Reranker alone sufficient: **NO**.