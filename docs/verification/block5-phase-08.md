# Block 5 Phase 08 — Block 4 to Block 5 integration

Status: PASS

Canonical document: `sample_legal.pdf`.

Query: `bảo hiểm hưu trí bổ sung người lao động`.

Flow executed with the real frozen Block 4 retrieval service, followed by Block 5 using the deterministic test-only Unicode-codepoint counter:

```text
retrieved candidate count: 8
retrieval final ranks: 1,2,3,4,5,6,7,8
duplicate count: 0
selected source IDs: S1,S2,S3,S4
selected retrieval ranks: 1,2,3,4
selected chunk IDs:
  6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1
  e3e6bd37-81aa-470c-bbc1-4e596ce51b81
  5a5aeeb5-ce90-41de-837c-332bd208f897
  c45e3d45-7183-42c5-8d65-9917878e1f6d
context token count: 2283
context budget: 2500
budget exhausted: true
stop reason: TOKEN_BUDGET
Block 5 database queries: 0
```

Short context preview:

```text
[Evidence S1]
Nguồn: Nghị định số 135/2026/NĐ-CP — Quy định cơ chế, chính sách ưu đãi, ưu tiên...

Nội dung:
2. Đơn vị vận hành hệ thống điện và thị trường điện được hưởng các cơ chế, chính sách ưu đãi...
```

The token count validates Block 5 mechanics only; it is not claimed to be a final Generation tokenizer count.
