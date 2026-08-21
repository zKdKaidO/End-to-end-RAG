# Supported-Case Abstention Calibration V1

This directory is an offline Block 6 diagnostic. It does not register prompt
variants with the production prompt loader and does not change the production
`GenerationProfile`. All variants use the same frozen evidence snapshots,
qwen3.5:9b, tokenizer, deterministic status parser, citation parser, and
generation options as `legal-rag-v2`.

Run inside the API container:

```text
python -m evaluation.experiments.abstention_calibration_v1.runner
```

Use `--fresh` only to discard experiment progress and repeat provider calls.

