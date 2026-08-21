# Evidence Presentation + Status/Citation Stability Experiment V1

This package is an offline diagnostic harness. It reads the frozen Evaluation
V2 hierarchy snapshot, rebuilds the frozen Block 5 context with the production
tokenizer, and calls the real configured `qwen3.5:9b` provider.

It does **not** register prompts, alter retrieval, select new evidence, change
the context budget, or modify Blocks 1–6. Ground-truth-aware strategies are
explicitly labelled `ORACLE` and are excluded from production-candidate
selection.

Run inside the API container:

```text
python -m evaluation.experiments.evidence_presentation_v1.runner
```

Progress is checkpointed in `raw_progress.json`, so an interrupted real-model
run can resume without duplicating completed generations. Use `--fresh` only
when intentionally starting a new experimental measurement.

