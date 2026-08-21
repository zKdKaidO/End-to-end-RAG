# Multi-Evidence Retrieval Experiment V1 — Final Verification

Final status: **COMPLETE**

The frozen nine-case multi-piece subset was diagnosed using real V2 retrieval snapshots, canonical `block3-v1` corpus records, frozen Block 5, and real Block 6 only for the selected finalist. No production behavior or frozen dataset was changed.

Principal result: bounded direct-child hierarchy expansion was the best offline strategy. It improved complete multi-piece retrieval from 3/9 to 6/9 and required-evidence recall from 46.67% to 81.11%, while improving all-answerable Hit@10 from 85.45% to 92.73% and preserving Hit@1. Real Block 5 retained all expected evidence H2 retrieved, although average context utilization rose and 11/55 cases exhausted the token budget.

Candidate coverage establishes that reranking is not the next defensible primary intervention: seven required references were absent from both frozen branch pools, and only 3/9 complete acceptable evidence sets existed anywhere in the pool. A perfect reranker therefore could not exceed the 33.33% production complete-case rate.

Real H2 generation replay completed 4/6 affected cases and false-abstained on 2/6. Retrieval improvement is thus necessary but not sufficient for end-to-end quality. The supported-case abstention problem remains a separate future experiment.

Recommended next production-design target: **LEGAL HIERARCHY RETRIEVAL V2**, beginning with bounded direct-child expansion plus explicit context-budget/ordering safeguards. Confidence: medium due to the small three-document corpus and nine multi-piece cases.

Separately, Phase 00 confirmed a genuine `v1` versus `block3-v1` automatic integration defect. It did not affect canonical experiment data and was not changed in this diagnostic phase. A future narrow compatibility correction should centralize the canonical version constant and regression-test the automatic hook.

Regression: backend 212/212 passed with 8 warnings in 91.03 seconds; frontend 11/11 passed; production build passed. Final decision: **READY FOR TARGETED RETRIEVAL DESIGN**.

