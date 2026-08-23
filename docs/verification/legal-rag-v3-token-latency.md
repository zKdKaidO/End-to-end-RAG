# Legal-RAG-V3 Token and Latency Verification

Date: 2026-08-22

Token counts use the real `Qwen/Qwen3.5-9B` tokenizer/chat template, thinking disabled, P0, and all 65 frozen contexts.

| Prompt | Mean | Median | Min | Max | P95 | Overflow |
|---|---:|---:|---:|---:|---:|---:|
| V2 | 2860.38 | 2548 | 1304 | 4508 | 4380.4 | 0 |
| V3 | 2836.38 | 2524 | 1280 | 4484 | 4356.4 | 0 |

Paired V3 − V2 delta: exactly -24 tokens for all 65 cases. Selected evidence and Block 5 context tokens are identical; no evidence was dropped by V3 implementation. Maximum V3 prompt + 512 output + 32 guard = 5,028, below the 32,768 hard limit.

Same-run 55-answerable latency is observational:

| Metric | V2 mean / median / P95 ms | V3 mean / median / P95 ms |
|---|---:|---:|
| TTFT | 1217.8 / 1073.1 / 1849.7 | 1205.5 / 1052.1 / 1883.6 |
| Generation | 2137.2 / 2138.6 / 3040.7 | 2212.7 / 2237.7 / 3403.4 |
| Measured generation-call total | 2147.3 / 2148.2 / 3049.9 | 2221.8 / 2246.1 / 3410.7 |

Mean completion tokens: V2 57.36; V3 62.78. Sequential local-provider timing includes warm-up/order effects and is not an SLA.
