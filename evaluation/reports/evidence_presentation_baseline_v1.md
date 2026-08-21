# Evidence Presentation Baseline V1

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Production prompt: `legal-rag-v2`
- Production prompt SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- Production changed: **NO**

## Repeated complete-context false-abstention cases

| Case | ANSWERABLE | INSUFFICIENT | Grounded | Classification |
|---|---:|---:|---:|---|
| `v2_bank_scope_ratios` | 0 | 3 | 0 | STABLE |
| `v2_bank_below_80_measures` | 0 | 3 | 0 | STABLE |
| `v2_civil_scope` | 0 | 3 | 0 | STABLE |
| `v2_cross_document_effective_dates` | 3 | 0 | 3 | NOT_REPRODUCED |


Targeted repeated baseline: answerable 25.00%, false abstention 75.00%, grounded expected-source conversion 25.00%.

Successful answerable controls: {'ANSWERABLE': 18}; grounded conversion 100.00%.

Unanswerable controls: {'INSUFFICIENT_EVIDENCE': 30}; unsupported direct answers 0.
