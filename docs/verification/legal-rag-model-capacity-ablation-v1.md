# Legal-RAG Model Capacity Ablation V1 — Verification

## Integrity

- Evaluation V1 hash: PASS
- Evaluation V2 hash: PASS
- Legal-RAG-V2 hash: PASS
- Legal-RAG-V3 hash: PASS
- E1 strict hash: PASS
- Production model/prompt: `qwen3.5:9b` / `legal-rag-v2`

## Preflight regression

- Backend: 245 passed, 0 failed, 8 warnings, 93.20 seconds
- Frontend: 11 passed, 0 failed
- Frontend build: PASS

## Feasibility gate

- Selected: `qwen3.5:27b` Q4_K_M, 27.8B, 17 GB
- Default Ollama load: FAIL twice, CUDA flash-attention initialization crash
- Supported no-flash smoke: PASS
- Placement: 28% CPU / 72% GPU
- VRAM: 15,785 MiB used, 266 MiB free
- Free RAM: 1.26 GiB
- Smoke throughput: 0.251 generated tokens/s
- Operational feasibility: FAIL
- Stop rule applied: PASS
- Context/settings reduced: NO
- Alternate family substituted: NO

## Experiment execution

- Frozen Block 5 contexts fingerprinted: 65/65
- Targeted A/B/C/D generations: 0/100
- Full V2 generations: NOT RUN
- Synthetic diagnostics: NOT RUN
- Candidate safety: NOT RUN
- Quality conclusion: INCONCLUSIVE

## Production impact

- Blocks 1-5: UNCHANGED
- Block 6 production prompt/model: UNCHANGED
- Retrieval/context/parsers/SSE: UNCHANGED
- Database schema: UNCHANGED
- Experimental model promoted: NO
- Temporary experimental server: STOPPED

## Post-experiment regression

- Backend: 245 passed, 0 failed, 8 warnings, 93.73 seconds
- Frontend: 11 passed, 0 failed
- Frontend build: PASS
