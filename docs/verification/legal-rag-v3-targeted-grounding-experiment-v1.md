# Legal-RAG-V3 Targeted Grounding Experiment V1 — Verification

Generated: 2026-08-22T08:13:06.053697+00:00

- Frozen hash verification: PASS
- E1/E2 frozen before provider evaluation: PASS
- Targeted real generations: 75
- Full answerable records: 165
- Safety real generations: 0
- Synthetic real generations: 54
- LLM judge: NOT USED
- Production default: legal-rag-v2
- Production legal-rag-v3 hash unchanged: PASS
- Blocks 1–5, parsers, SSE, schema: UNCHANGED

## Final regression

- Backend: 245 collected, 245 passed, 0 failed, 8 warnings, 90.31 seconds.
- Frontend: 5 files and 11 tests passed, 0 failed, 1.32 seconds.
- Production frontend build: PASS; 30 modules transformed in 166 ms.

The pytest summary completed successfully before the surrounding Docker pipe was interrupted after lingering; the pytest result is authoritative.

Final decision: neither E1 nor E2 is a production candidate. The experiment supports prompt-contract sensitivity but also shows persistent complete-evidence failures and strong multi-evidence over-abstention. A controlled 9B-versus-larger-model capacity ablation is justified as the next isolated experiment; no model change was made here.
