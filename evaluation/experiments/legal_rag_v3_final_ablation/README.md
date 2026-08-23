# Legal-RAG-V3 Final Ablation + Design Gate

This offline harness compares the exact
`legal-rag-v3-compact-fewshot-experimental` prompt with:

- A: P0 frozen production evidence presentation
- B: P1 structural anchor/direct-child presentation

It reuses frozen Evaluation V2 Block 4/5 snapshots and the real configured
`qwen3.5:9b` provider. It does not register the experimental prompt, alter the
GenerationProfile, or modify Blocks 1–5.

Run inside the API container:

```text
python -m evaluation.experiments.legal_rag_v3_final_ablation.runner --fresh
```

Every provider result is checkpointed in `raw_progress.json`.
