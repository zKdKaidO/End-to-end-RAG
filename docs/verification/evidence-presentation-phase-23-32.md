# Evidence Presentation Experiment — Phases 23–32

## Full 55-answerable + 10-unanswerable finalists

| Combination | Acceptance | False abstention | Grounded expected source | Citation validity | Status validity | Safety |
|---|---:|---:|---:|---:|---:|---:|
| compact + P1 | 92.73% | 7.27% | 90.91% | 92.73% | 100% | 10/10, 0 unsupported |
| compact few-shot + P1 | **94.55%** | **5.45%** | **92.73%** | **94.55%** | **100%** | 10/10, 0 unsupported |
| compact + P0 | 92.73% | 7.27% | 90.91% | 92.73% | 100% | 10/10, 0 unsupported |
| legal-rag-v2 + P1 | 89.09% | 10.91% | 89.09% | 89.09% | 100% | 10/10, 0 unsupported |

Frozen one-run production baseline: 87.27% acceptance/citation validity,
12.73% false abstention, and 85.45% expected-source match.

## Best combination breakdown

- single-evidence: 95.65% grounded (44/46 accepted; both accepted metrics align)
- multi-evidence: 77.78% expected-source grounded; 88.89% accepted
- hierarchy-recovered: 5/5 accepted, cited, and expected-source matched
- multi-document: 1/1 accepted, cited, and expected-source matched

The three remaining best-combination abstentions were
`v2_social_applicable_groups`, `v2_bank_actual_capital_formula`, and
`v2_civil_scope`. One additional answered case cited a structurally valid but
non-ground-truth source (`v2_social_effective_transition`); no semantic
correctness claim is made for that case.

## Context stratification

Frozen false-abstention rates by data-derived context bucket were 11.11% low,
5.88% medium, and 5.88% high. Long context therefore does not correlate with
false abstention overall, although civil scope remains a clear case-specific
distraction pattern. Cases with hierarchy children showed 11.11% frozen false
abstention versus 0% without, but also had slightly larger contexts; causality
is not established.

## Tokens and latency

Best combination mean prompt tokens: 2,668.7, a reduction of 144.3 versus the
same 55-case frozen production baseline. Mean TTFT improved by 288.4ms and mean
generation time improved by 386.4ms. There is no second model call. These are
small local measurements, not an SLA or a production performance claim.

