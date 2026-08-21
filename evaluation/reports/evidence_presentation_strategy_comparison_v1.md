# Evidence Presentation Strategy Comparison V1

All P1–P6 strategies preserve the selected evidence set and use runtime-available fields only. No strategy uses expected chunk IDs or labels.

| Strategy | Targeted answerable | Targeted grounded | Citation valid | Expected source | Safety abstention | Unsupported | Status valid | Mean prompt tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 | 25.00% | 25.00% | 25.00% | 25.00% | 100.00% | 0 | 100.00% | 2620.5 |
| P1 | 50.00% | 50.00% | 50.00% | 50.00% | 100.00% | 0 | 100.00% | 2531.0 |
| P2 | 25.00% | 25.00% | 25.00% | 25.00% | 100.00% | 0 | 100.00% | 2481.0 |
| P3 | 25.00% | 25.00% | 25.00% | 25.00% | 100.00% | 0 | 100.00% | 2620.5 |
| P4 | 25.00% | 25.00% | 25.00% | 25.00% | 100.00% | 0 | 100.00% | 2620.5 |
| P5 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0 | 100.00% | 2613.5 |
| P6 | 25.00% | 25.00% | 25.00% | 25.00% | 100.00% | 0 | 100.00% | 2616.5 |

Selected diagnostic presentation: **P1**. Selection used only measured model behavior and runtime-plausible strategy definitions; it did not use ground truth in the algorithm itself.
