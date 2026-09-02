# ZKD Compute Product Phase 5C.2A — Local Document Lifecycle Completion

## Scope

This phase completes the non-visual, device-local document lifecycle. It adds no DocumentsPage or AskPage integration and does not change Core RAG ranking, context, generation, platform document APIs, or frozen architecture contracts.

## Local delete and list routes

| Route | Required local operation | Purpose |
| --- | --- | --- |
| `GET /v1/documents` | `documents` | Authoritative safe metadata list for the selected device. |
| `DELETE /v1/documents/{document_id}` | `documents` | Remove the local document and durable local artifacts. |

Both routes use the existing exact-Origin browser-session HMAC envelope. The delete route accepts an opaque UUID only. An unknown UUID returns the existing `DOCUMENT_NOT_FOUND`; a repeated browser delete is therefore not silently treated as success.

## Cleanup semantics

Deletion is serialized per document with preparation and indexing. It first marks active local jobs cancelled, removes only the managed `documents/<UUID>` and `artifacts/<UUID>` trees, then removes matching local jobs, artifact rows, and catalog metadata. Missing managed source/artifact resources are safe no-ops; unexpected filesystem failures return a typed local error rather than falsely reporting successful cleanup.

The catalog foreign-key boundary and document lock prevent a late preparation/index mutation from restoring a deleted catalog identity. Retrieval is not changed: after deletion it fails to find the scoped local document because its catalog/artifact data is genuinely absent.

## Manifest tombstone and outage behavior

After local cleanup, the catalog persists one coalesced metadata-only tombstone:

```json
{
  "document_id": "<opaque UUID>",
  "preparation_state": "DELETED",
  "index_state": "DELETED",
  "local_availability": "DELETED",
  "chunk_count": 0
}
```

No PDF bytes, text, chunks, vectors, prompts, or answers are enqueued. Per-document outbox coalescing replaces an older pending `INDEX_READY` payload with the newer deletion revision. A valid established local session can delete during a platform outage; the outbox delivers when the control channel recovers.

## Listing contract

`GET /v1/documents` returns only `document_id`, original filename, byte size, preparation/index state, safe typed failure, timestamps, and page/chunk counts. It never returns paths, source hashes, page text, chunks, vectors, credentials, or artifact databases. This is distinct from the platform manifest read model: while the selected device is available, this local catalog list is authoritative for local operations.

## Browser client handoff

`BrowserComputeClient` now exposes:

```ts
const documents = await compute.listDocuments();
await compute.deleteDocument(documentId);
```

`deleteDocument` uses the existing single authenticated request builder with `DELETE`, the empty raw-body SHA-256, fresh nonce, HMAC, and no automatic retry after an uncertain network failure.

## Verification

Focused temporary-root coverage verifies authorized/unauthorized delete behavior, list privacy, failed and orphaned cleanup, retrieval-before/delete and absence-after/delete, outbox replacement, and outage/recovery manifest delivery. No normal development corpus document is created.

## Known limitations and next phase

DocumentsPage and AskPage are not yet switched to local Compute. Chrome/Edge PNA/CORS validation, custom URI, OS credential-store hardening, installer packaging, and authenticated real generation remain separate work.

Next phase: `P2C.5C.2B DOCUMENTS LOCAL-FIRST PRODUCT WIRING`.
