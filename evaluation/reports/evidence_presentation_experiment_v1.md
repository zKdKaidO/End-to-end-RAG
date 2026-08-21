# Evidence Presentation + Status/Citation Stability Experiment V1

## Frozen state

- V1: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- V2: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Production prompt: `legal-rag-v2`
- Production changed: **NO**

## Oracle ceilings (not production eligible)

- Minimal sufficient evidence: answerable 50.00%, grounded 50.00%.
- Expected evidence first in full context: answerable 50.00%, grounded 50.00%.

## Best measured joint combination

- Combination: `compact-fewshot|P1`
- Targeted false abstention: 75.00% → 25.00%
- Full answerable acceptance: 87.27% → 94.55%
- Full citation validity: 87.27% → 94.55%
- Full expected-source match: 85.45% → 92.73%
- Status validity: 100.00%
- Unanswerable abstention: 100.00%
- Unsupported direct answers: 0
- Mean prompt-token delta vs production P0: -144.29090909090928
- Mean TTFT delta vs production P0: -288.40ms
- Mean generation-latency delta: -386.4149184363914

## Full-corpus causal controls

| Combination | Acceptance | False abstention | Citation valid | Expected source | Status valid | Unanswerable |
|---|---:|---:|---:|---:|---:|---:|
| compact + P0 | 92.73% | 7.27% | 92.73% | 90.91% | 100% | 10/10 |
| legal-rag-v2 + P1 | 89.09% | 10.91% | 89.09% | 89.09% | 100% | 10/10 |
| compact + P1 | 92.73% | 7.27% | 92.73% | 90.91% | 100% | 10/10 |
| compact few-shot + P1 | **94.55%** | **5.45%** | **94.55%** | **92.73%** | **100%** | **10/10** |

All four produced zero unsupported direct answers. Compact+P0 passes the full
acceptance rules and outperforms presentation-only P1, so the primary measured
effect is prompt-contract simplification. P1 adds a smaller joint improvement.

## Context findings

`v2_civil_scope` still abstained under every production-plausible finalist. It
has one supporting block first, followed by about 3,482 tokens across 16
diagnostic distractor blocks. This is strong case-specific distraction evidence,
but context length did not correlate with false abstention across the complete
answerable sample (r = -0.056). Context selection/presentation remains a
secondary research target, not a general threshold rule.

## Status and citation stability

The old combined-prompt duplicate marker reproduced identically in 3/3 new raw
provider outputs and remained invalid under the unchanged strict parser. The
new compact finalists had 100% status validity. Citation validation and the
exact `[S<n>]` parser were unchanged.

## Oracle gap

Under unchanged legal-rag-v2, both minimal and evidence-first oracle runs were
50% grounded on the targeted set, while the best production-plausible joint
combination was 75%. The oracles therefore expose a prompt-specific ceiling;
they do not show that ground-truth context selection is required for the three
cases recovered by compact prompting.

## Decision

**LEGAL-RAG-V3 DESIGN**

The best candidate satisfied every acceptance rule and may proceed to a separate production-design phase.

This is diagnostic evidence only. No prompt or evidence-presentation strategy was deployed.

Known limitations: only ten frozen unanswerable controls exist; expected-source
match is not semantic entailment; the full finalist measurement is one run per
case; context/distractor correlations are descriptive; and
`v2_social_effective_transition` requires human review because it used a
structurally valid source outside the frozen acceptable set.
