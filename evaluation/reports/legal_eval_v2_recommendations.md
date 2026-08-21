# Legal Evaluation V2 — Recommended Next Experiments

These are evidence-based research recommendations only. No quality fix is implemented or approved by this report.

## Priority 1: Multi-evidence coverage and legal-hierarchy retrieval research

- Measured affected cases: 6 / 55 answerable (10.91%).
- Case IDs: `['v2_social_scope', 'v2_social_applicable_groups', 'v2_social_practice_content', 'v2_social_effective_transition', 'v2_bank_scope_ratios', 'v2_bank_loan_limit_exceptions']`
- Why: Complete multi-evidence sets were frequently absent from final Top-10 even when several required chunks existed in the dense pool.
- Suggested experiment: Replay frozen branch snapshots to compare coverage-aware fusion, legal-hierarchy expansion, and reranking; require complete-set gains rather than raw candidate volume.
- Architecture/latency impact: Medium-to-high impact if adopted; reranking adds latency, while hierarchy-aware retrieval changes Block 4 semantics.

## Priority 2: Single-evidence candidate-generation and document-disambiguation research

- Measured affected cases: 2 / 55 answerable (3.64%).
- Case IDs: `['v2_social_course_modes', 'v2_bank_board_loan_threshold']`
- Why: A small number of single-chunk questions missed the expected evidence entirely, including one wrong-document case.
- Suggested experiment: Offline ablate document metadata constraints and legal-identifier-aware query representation on only the affected cases.
- Architecture/latency impact: Medium impact; requires reliable metadata and must be recall-tested against all V2 cases.

## Priority 3: Supported-case abstention calibration research

- Measured affected cases: 2 / 55 answerable (3.64%).
- Case IDs: `['v2_civil_scope', 'v2_civil_effect_and_repeal']`
- Why: Complete expected evidence reached Block 5, but the frozen generator abstained on two answerable cases.
- Suggested experiment: Diagnose prompt/evidence presentation on the captured traces; compare prompt-only variants offline without weakening hard-negative abstention.
- Architecture/latency impact: Low-to-medium impact if prompt-only; must preserve the measured 10/10 unsupported-case abstention result.

## Decision guardrails

- Do not adopt reranking merely because it is fashionable; require measurable Top-50-to-Top-10 recoveries.
- Do not use retrieval similarity as an answerability threshold.
- Preserve the immutable V2 dataset/hash for every future comparison.
