# Legal-RAG-V3 Rollout and Rollback Design

Status: **PROCEDURE DESIGN — DO NOT EXECUTE YET**

## Control plane

Prompt choice remains server-owned. The current control is `GENERATION_PROMPT_VERSION`, loaded by settings into the frozen `GenerationProfile`. Normal requests, internal evaluation requests, and Ask UI requests cannot supply or override it. Debug UI may display `prompt_version` from `DebugTrace` and SSE start metadata but cannot mutate it.

The current architecture reads settings at process startup. Therefore V3 activation and rollback use a controlled API container recreation/restart; hot reload is not assumed. No frontend switch is added.

## Preconditions for future rollout

1. Obtain explicit implementation/activation approval.
2. Verify both frozen dataset hashes and the V2 prompt hash.
3. Copy `docs/design/legal-rag-v3-prompt.txt` byte-for-byte to `app/prompts/legal-rag-v3.txt`.
4. Verify the runtime copy SHA-256 is `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf`.
5. Add `legal-rag-v3` to the existing profile and loader allowlists without changing their structure or error semantics.
6. Run all unit, parser, streaming, real evaluation, repeated safety, restart, backend, frontend, and build gates in [legal-rag-v3-validation-plan.md](legal-rag-v3-validation-plan.md).
7. Preserve `app/prompts/legal-rag-v2.txt` unchanged and record both hashes in the release evidence.

## Activation procedure

After all gates and human approval:

1. Change only the server-owned deployment value from `GENERATION_PROMPT_VERSION=legal-rag-v2` to `GENERATION_PROMPT_VERSION=legal-rag-v3`.
2. Recreate the API process so Compose reloads `.env` rather than relying on a simple restart:

   ```text
   docker compose up -d --no-deps --force-recreate api
   ```

3. Do not recreate PostgreSQL, Redis, MinIO, workers, or volumes.
4. Verify API health and make one controlled answer request.
5. Confirm internal diagnostics and SSE `start` show `prompt_version=legal-rag-v3`, while the full prompt remains absent from logs/responses.
6. Confirm the returned marker is stripped, citations map normally, and database schema/table count is unchanged.
7. Record deployment time, V2/V3 hashes, image/build identity, profile values, health result, and smoke trace request ID.

No database migration, reindex, retrieval change, Block 5 change, frontend change, or worker restart is part of activation.

## Rollback triggers

Rollback immediately if controlled production verification detects any of:

- malformed, missing, unknown, or duplicate status markers;
- unsupported direct answers on an insufficient-evidence control;
- citation/parser/provenance regression;
- prompt hash mismatch;
- unexpected prompt selection or client-controlled override;
- prompt-budget overflow attributable to V3;
- streaming marker leakage or unsafe insufficient continuation;
- material quality regression confirmed by the approved gate owner.

These triggers reuse existing failure semantics; V3 adds no new runtime error category.

## Exact rollback procedure

1. Set the server-owned deployment value back to `GENERATION_PROMPT_VERSION=legal-rag-v2`.
2. Recreate only the API service so it reloads the environment:

   ```text
   docker compose up -d --no-deps --force-recreate api
   ```

3. Verify API health.
4. Confirm internal diagnostics/SSE start show `prompt_version=legal-rag-v2`.
5. Verify `app/prompts/legal-rag-v2.txt` SHA-256 remains `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`.
6. Run a controlled answer and streaming smoke check, confirming existing status/citation behavior.
7. Record the rollback request ID, timestamps, hashes, and reason.

The V3 file may remain as an inactive immutable historical artifact. Do not delete or overwrite either version during rollback.

## Rollback impact

| Operation | Required? |
|---|---|
| Database change | No |
| Reindexing | No |
| Retrieval restart/change | No |
| Block 5 change | No |
| Model/provider change | No |
| Frontend change | No |
| API process recreation | Yes, because settings are startup-owned |
| Volume deletion | Never |

## Observability

The authoritative runtime signal is the existing `prompt_version` field in generation results, DebugTrace, and SSE start events. The canonical hash remains release/test evidence. If a future internal startup log adds `prompt_hash`, it must log only the hash, never the prompt body, and must not require a public schema change for V3 activation.
