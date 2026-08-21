# Legal Hierarchy Retrieval V2 — Retrieval Before/After

Dataset SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`

| Metric | Before | After |
|---|---:|---:|
| Hit@1 | 63.64% | 61.82% |
| Hit@3 | 74.55% | 72.73% |
| Hit@5 | 83.64% | 87.27% |
| Hit@10 | 85.45% | 90.91% |
| MRR | 0.7087 | 0.7089 |
| Multi-evidence complete | 33.33% | 77.78% |
| Required-evidence recall | 46.67% | 83.33% |

- H2 parity: **PASS**
- Average base / children / combined: 10.00 / 4.09 / 14.09
- Bounds violated: 0
- Hierarchy-recovered expected chunks: 12 across 5 cases.

Per-case candidate identities, immutable base RRF anchors, hierarchy diagnostics, and expected-evidence metrics are in the JSON artifact.
