# Block 2 → Block 3 Input Contract Amendment: Token-Safe Legal Chunking

Verified: 2026-08-24 (Asia/Saigon)

## Result

The narrow producer/consumer repair is implemented and the confirmed production document now completes both processing and indexing. The amendment-specific suite passes 23/23. The final repository-wide run completed with 310 passed and three live-corpus identity failures caused by the existing development database state; the frozen datasets and retrieval behavior were not changed to conceal those failures.

## Root cause and invariant

Block 2 previously bounded candidates by characters and persisted them without applying Block 3's exact multilingual-E5 input rule. Block 3 correctly evaluated the complete `passage: `-prefixed string and rejected eight persisted chunks over 512 tokens. This was a producer/consumer contract mismatch, not a Block 3 embedding failure.

Block 2 now guarantees for every final chunk:

```text
len(exact_E5_tokenizer.encode("passage: " + chunk.embedding_text)) <= 512
```

The exact combined input, including prefix, legal header, separators, and tokenizer special tokens, is the only pass/fail authority. The dynamic budget is used only to propose hard-fallback boundaries. A complete validation pass runs after generation and another defensive pass runs before the processing repository acquires lifecycle locks or performs deletes/inserts. Block 3 retains its own exact guard.

## Narrow implementation

- `app/indexing/input_contract.py`: canonical E5 model, prefix, tokenizer-only offline loader, exact counters/validator, centralized headroom, minimum-content, overlap, and forward-progress constants.
- `app/processing/chunker.py`: frozen normal candidate path followed by token-aware semantic and hard-token fallbacks.
- `app/processing_worker_main.py`: final CHUNKING-stage producer validation and exclusive-end exact page/provenance mapping.
- `app/repositories/processing_repo.py`: atomic pre-persistence contract fence before any durable mutation.
- `app/indexing/embedder.py`: uses the shared input construction/counting rules while preserving SentenceTransformer encoding, normalization, batching, and the defensive `EmbeddingInputTooLongError` behavior.
- `docker-compose.yml`: processing-worker reuses `model_cache` with Hugging Face/Transformers offline mode.
- `deployment/docker-compose.recovery-test.yml`: recovery processing-worker reuses the same recovery model cache.
- `tests/unit/test_token_safe_chunker.py`: deterministic normal, semantic, hard-token, offset, Unicode, overlap, hierarchy, page mapping, and invariant coverage.
- `tests/integration/test_processing_embedding_contract.py`: controlled CHUNKING failure with zero partial reconstruction, legal-unit, chunk, or indexing-job persistence.

No migration or schema file was added or modified.

## Three processing paths

1. Normal: existing legal-aware character/sentence output is built exactly as before. If the exact final E5 input fits, content and embedding text remain unchanged.
2. Semantic fallback: oversized candidates are recursively divided at blank lines, newlines, then sentence boundaries; pieces are greedily repacked in source order. Semantic splits have zero overlap.
3. Hard fallback: used only when a single semantic block still does not fit. A fast tokenizer returns token-to-original-character offsets; chunks are sliced directly from the immutable reconstructed source. Token IDs are never decoded and text is never truncated or Unicode-normalized.

The hard path calculates effective overlap as the configured overlap capped so every iteration advances by at least `MIN_FORWARD_PROGRESS_TOKENS`. It also explicitly rejects `next_start <= token_start`. If the exact fixed header leaves fewer than `MIN_CONTENT_TOKENS`, `EmbeddingHeaderTooLongError` terminates processing rather than creating microscopic chunks.

Outer whitespace removal shifts the exact source start/end offsets by counted leading/trailing whitespace. It does not use `.find()` or textual re-search, so repeated legal text remains unambiguous. `char_end` is exclusive; page end is mapped from `char_end - 1`. Split children retain the identical `LegalUnitData`/persisted `legal_unit_id`, hierarchy metadata, and source order.

## Focused test evidence

Command:

```text
docker compose exec -e PYTHONPATH=/app api python -m pytest tests/unit/test_chunker.py tests/unit/test_embedder.py tests/unit/test_token_safe_chunker.py tests/integration/test_processing_embedding_contract.py tests/integration/test_processing_worker_failures.py -v
```

Result: **23 passed, 0 failed, 6 warnings in 7.10s**.

This includes exact-limit acceptance, one-token-over splitting, Vietnamese prose and offsets, giant paragraph/sentence/no-punctuation inputs, table-like input, semantic zero overlap, hard-token controlled overlap, dynamic overlap reduction, strict progress, header exhaustion, repeated text, deterministic rerun, legal-unit identity, multi-page provenance, exact final-token invariant, Block 2 atomic failure, and the existing Block 3 guard.

Compose validation:

- development: PASS;
- recovery: PASS using `.env`;
- resolved processing-worker: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `model_cache -> /root/.cache/huggingface`.

The processing worker loaded only the cached fast tokenizer. No E5 PyTorch weights were instantiated for chunking.

## Real production-defect regression

Document: `15206eca-7e5e-49d0-9788-24fc09b8ea76`

Before:

- pages: 55;
- legal units: 229;
- chunks: 249;
- indexes: 0;
- oversized exact prefixed inputs: 8;
- maximum reported exact prefixed input: 2535 in the Block 3 failure.

After two deterministic reprocessing runs:

- latest processing job `43540dfb-c5de-4ab9-ab17-88d398d7bbd5`: `COMPLETED / DONE`;
- latest indexing job `044d7754-01ea-4819-a19f-415f988475a3`: `COMPLETED / FINALIZE`;
- legal units: 229;
- final chunks: **270**;
- final indexes: **270**;
- exact maximum of `passage: ` plus final `embedding_text`: **512**;
- oversized chunks: **0**;
- path counts: **241 NORMAL**, **29 SEMANTIC**, **0 HARD_TOKEN**.

All 241 formerly valid normal candidates remained on the normal path. The eight oversized parents became 29 semantic children. The real document did not require hard-token fallback.

Persisted split provenance contains exact source character spans and recomputed child page ranges. The large former page 9–14 parent, for example, is represented by children mapped to 9, 9–10, 10–11, 11–12, 12–13, 13, and 13–14 rather than copying 9–14 to every child.

## Full regression evidence

Command:

```text
docker compose exec -e PYTHONPATH=/app api python -m pytest tests -v
```

Result: **313 collected, 310 passed, 3 failed, 8 warnings in 97.24s**.

The three failures are live-data identity assertions outside this amendment:

1. Evaluation V1 references frozen document `89eebb70-2020-45c0-a6f0-44d292f4a49b`, which is absent from the normal development database.
2. Evaluation V2 references frozen documents `3fb22b9b-ed46-4e04-97e2-b8c854f8252b`, `78e54e57-fc2e-47b2-919c-c7120776226d`, and `ed9f3e56-f3cd-41f6-9ed9-8b70e7f44c25`, which are absent from that database.
3. The canonical sample was previously reprocessed and its current top lexical chunk is `1f11274b-9614-4b5f-8a1d-aea973325914`, while the frozen live assertion expects `b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4`.

The two initially observed Qwen tokenizer tests passed after the already-verified 22 MB tokenizer artifact was copied from the existing recovery model cache into the existing normal `rag_model_cache`; there was no network download or application change. The remaining corpus was deliberately not rewritten, IDs were not remapped, and evaluation ground truth was not weakened.

## Freeze and limitations

- Database schema: unchanged.
- Block 3 embedding algorithm: unchanged; defensive exact guard retained.
- Retrieval, hierarchy expansion, RRF, and hydration: unchanged.
- Block 5 context construction: unchanged.
- Block 6 generation and prompts: unchanged.
- Authentication, storage, and frontend: unchanged.
- Architecture: unchanged except the approved processing-worker access to the existing offline tokenizer cache.
- No truncation, token decoding, new tables, new services, LangChain, or LlamaIndex.

Known limitation: token-safe splitting preserves exact source text, hierarchy, and provenance, but does not reconstruct semantic column context in large multi-page tables or appendices whose column headers are separated from later rows. No speculative table-header repetition was added.

