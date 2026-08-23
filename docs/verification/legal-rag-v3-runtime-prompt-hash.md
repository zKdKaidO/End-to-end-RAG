# Legal-RAG-V3 Runtime Prompt Hash Verification

Date: 2026-08-22

| Artifact | SHA-256 | Bytes | Result |
|---|---|---:|---|
| Evaluation V1 | `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245` | — | unchanged |
| Evaluation V2 | `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842` | — | unchanged |
| Runtime `legal-rag-v2` | `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee` | — | unchanged |
| Approved V3 design | `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf` | 1,441 | exact |
| Runtime `legal-rag-v3` | `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf` | 1,441 | exact |

Design/runtime V3 byte comparison: **IDENTICAL**. Serialization is UTF-8 without BOM, LF only, and one trailing LF. The runtime prompt was copied from the approved artifact and was not tuned after validation results.
