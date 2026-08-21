# Block 6 Phase 14 — Canonical real RAG E2E

- Query: `Người lao động được hưởng quyền lợi gì từ bảo hiểm hưu trí bổ sung?`
- Document filter: `89eebb70-2020-45c0-a6f0-44d292f4a49b` (`sample_legal.pdf`)
- Retrieval: 50 dense, 0 lexical, 10 fused/final candidates.
- Selected evidence: S1–S10, retrieval ranks 1–10.
- Context: 1,445 tokens; selected 10; no budget exhaustion.
- Prompt: local 1,670; Ollama 1,670; guard PASS.
- Model/prompt: `qwen3.5:9b` / `legal-rag-v1`.
- Answer preview: identifies the supplementary retirement-insurance benefit and limits the answer to what the evidence specifies.
- Used/valid/invalid citations: `[S1]` / `[S1]` / none; validation PASS.
- S1 provenance: chunk `e3e6bd37-81aa-470c-bbc1-4e596ce51b81`, document above, page 6; exact mapping PASS.
- Usage: 1,670 input + 155 output = 1,825 total.
- Warm stream time to first token: 492.55ms; generation 2,789.25ms; total 2,852.02ms. Cold API path after restart: 10,767.70ms internal (13,065ms client measurement including tokenizer/API startup effects).

This verifies engineering integration, not independent semantic legal correctness. Real provider/model used; wording was not asserted.

Result: PASS.
