# Evidence Presentation Experiment — Phases 09–16

All strategies retained the exact frozen Block 5 selected chunk set and stayed
within the unchanged 4,096-token budget for all 65 cases.

| Strategy | Target answerable | Target grounded | Unanswerable abstention | Unsupported | Interpretation |
|---|---:|---:|---:|---:|---|
| P0 current | 25% | 25% | 100% | 0 | frozen presentation |
| P1 anchor/child group | 50% | 50% | 100% | 0 | best presentation-only screen |
| P2 minimal wrapper | 25% | 25% | 100% | 0 | no targeted gain |
| P3 query-overlap order | 25% | 25% | 100% | 0 | no targeted gain |
| P4 anchors then children | 25% | 25% | 100% | 0 | no targeted gain; largely matches current order |
| P5 explicit delimiters | 0% | 0% | 100% | 0 | rejected; worsened abstention |
| P6 stronger boundaries | 25% | 25% | 100% | 0 | no targeted gain |

P1 renders compact runtime facts such as `BASE` and `CHILD_OF=S1`, retains the
legal identity and content, and never merges sources or changes source IDs.
Its largest context was 4,015 tokens. P2 and P5 saved tokens but did not improve
targeted answerability, showing that token reduction alone was not sufficient.

The current system/user/evidence boundary is already explicit. P6 did not
improve the targeted cases, so boundary ambiguity is not supported as the
dominant cause.

