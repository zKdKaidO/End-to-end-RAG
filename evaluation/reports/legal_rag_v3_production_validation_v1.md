# Legal-RAG-V3 Production Validation V1

## Frozen inputs and isolation

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- V2 prompt SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- V3 prompt SHA-256: `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf`
- Evidence presentation: P0
- Production default after validation: `legal-rag-v2`
- Blocks 1–5 changed: **NO**

## Same-run full answerable comparison

| Metric | V2 | V3 |
|---|---:|---:|
| Answerable acceptance | 89.09% | 94.55% |
| False abstention | 10.91% | 5.45% |
| Citation presence | 89.09% | 94.55% |
| Citation validity | 89.09% | 94.55% |
| Expected-source match | 87.27% | 89.09% |
| Missing citation | 0.00% | 0.00% |
| Invalid citation | 0.00% | 0.00% |

## Repeated safety

- Runs: 30
- Structured abstentions: 30/30
- Unsupported direct answers: 0
- Status-marker failures: 0
- Answer/citation continuations after insufficient marker: 0

## Targeted five-run V3 repeatability

| Case | Answerable | Grounded | Citation valid | Expected source | Status valid |
|---|---:|---:|---:|---:|---:|
| `v2_bank_scope_ratios` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `v2_bank_below_80_measures` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `v2_civil_scope` | 0/5 | 0/5 | 0/5 | 0/5 | 5/5 |
| `v2_cross_document_effective_dates` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

## Multi-evidence breakdown

| Class | V2 grounded | V3 grounded |
|---|---:|---:|
| single_evidence | 91.30% | 93.48% |
| multi_evidence | 66.67% | 66.67% |
| hierarchy_recovered | 80.00% | 80.00% |
| multi_document | 100.00% | 100.00% |

## Tokens and latency

- Exact paired prompt-token delta V3 - V2: -24.0 tokens across 65 cases.
- Prompt-budget overflows: V2 0, V3 0.
- Mean TTFT: V2 1217.8 ms, V3 1205.5 ms.
- Mean generation: V2 2137.2 ms, V3 2212.7 ms.

## Activation readiness gate

- Engineering gate: **PASS**
- Human materiality/source review: **REQUIRED**
- Recommendation: **READY_FOR_ACTIVATION_REVIEW**

No activation was performed. The production default remains `legal-rag-v2`.
