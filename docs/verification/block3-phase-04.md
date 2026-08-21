# Phase 4 — E5 Model & Embedding Logic

## Files Inspected
- `app/indexing/embedder.py`
- `tests/unit/test_embedder.py`

## Files Created/Modified
- `app/indexing/embedder.py`
- `tests/unit/test_embedder.py`

## What was implemented
- Configured `intfloat/multilingual-e5-base`.
- Model output dimension verified at `768`.
- Tokenizer checks for input exceeding `512` tokens, raises `EmbeddingInputTooLongError` if exceeded (no silent truncation).
- Embeddings are generated in float32.
- Hardcoded string prefix `passage: ` is prefixed before every chunk text in `encode_batch`.
- Embeddings are L2 normalized automatically (`normalize_embeddings=True`).
- Setup `EMBEDDING_DEVICE=cpu`.

## Commands executed
- Wrote integration/unit tests for `E5Embedder`.

## Actual outputs
- Model generates correctly shaped and normalized embeddings.
- OOM/Too long inputs reliably throw error instead of silent truncation.

## Definition of Done
- `embedder.py` implemented.
- `intfloat/multilingual-e5-base` initialized.
- Float32 + L2 norm.
- `passage: ` prefix.
- Token limits enforced.
- Tested offline logic.
