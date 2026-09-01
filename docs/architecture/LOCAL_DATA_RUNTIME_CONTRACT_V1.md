# LOCAL_DATA_RUNTIME_CONTRACT_V1

**Project:** ZKD / Vietnamese Legal RAG
**Status:** **ACTIVE V1 LOCAL DATA/RUNTIME CONTRACT**
**Decision date:** 2026-09-01
**Depends on:** `LOCAL_FIRST_COMPUTE_ARCHITECTURE_V1.md` SHA-256 `932d2d4c3cbebb74c88a1fa65c6da9f2589b9523121bb91f175f204e64f21e90`
**Scope:** LocalComputeProvider persistence, artifact lifecycle, and local runtime boundaries

---

## 1. Scope and invariants

This contract freezes the V1 design for data owned by a user's future ZKD Compute installation. It does not implement the Browser-to-ZKD Compute protocol, desktop packaging, a local store adapter, frontend changes, a cloud provider, or a migration of the current development backend.

The platform web shell remains online independently of compute. If no capable provider is `READY`, the web shell disables Upload and does not accept PDF content. Platform cloud stores no raw PDF, page text, chunks, embeddings, index payloads, retrieved evidence, or context source content by default. LocalComputeProvider owns all of those artifacts.

The normal user must never install, operate, or troubleshoot PostgreSQL, Docker, Redis, MinIO, Python, pip, a command line, a database server, or worker commands. ZKD Compute owns its own internal lifecycle.

## 2. Application data root and layout

ZKD Compute resolves an OS-appropriate per-user application-data root at runtime. Windows V1 uses the equivalent of `%LOCALAPPDATA%\ZKD\Compute\`; the literal path is never hard-coded to a user name. The root is not the Git repository, Downloads, Desktop, current working directory, browser storage, or a temporary location.

```text
<application-data-root>/
  state/
    catalog.sqlite3              # local document/artifact/job catalog and manifest outbox
  documents/
    <document_id>/source.pdf     # managed immutable source copy
  artifacts/
    <document_id>/<artifact_id>/artifact.sqlite3
    <document_id>/<artifact_id>.staging/   # build-only; never queryable
  models/
    huggingface/hub/             # validated E5 cache; not per-document
  logs/
  tmp/                           # same-volume temporary writes and recoverable cleanup only
```

Each directory has one purpose. The runtime creates restrictive per-user permissions where the OS permits. `tmp` and `.staging` are never treated as a source of truth or surfaced as READY content.

## 3. Source PDF contract and deduplication

After future protocol admission confirms a capable provider is READY, ZKD Compute validates the PDF with the Block 1 semantic validator and computes SHA-256. It copies bytes to a same-volume temporary file, verifies the copied size/hash, then atomically moves it to `documents/<document_id>/source.pdf`. The managed copy, not the browser-selected path, is the future source of processing.

`document_id`, content SHA-256, original filename, MIME type, size, managed source path, and acceptance time are recorded in the local catalog. A filename is presentation metadata and is never an identity key.

| Input case | V1 behavior |
|---|---|
| Same bytes, same requested `document_id` | Idempotent acceptance; reuse the managed source and active artifact if compatible. |
| Same filename, different bytes | New document identity and managed source; never overwrite the existing document. |
| Same bytes, different filename or requested `document_id` | Reject with `DUPLICATE_CONTENT_REQUIRES_REUSE`; present the existing local document for explicit reuse. Do not silently create another source copy or alias. |

The local catalog enforces one active local document per content SHA-256 for the paired user's installation. A future explicit alias/copy feature requires its own identity and manifest rules.

## 4. Identity and artifact-version contract

The cloud control shell allocates a random, non-content-bearing UUID `document_id` only after provider admission. That UUID is also the local document primary key. It is immutable; replacing source bytes creates a new document rather than modifying an existing source in place.

| Identifier/value | Scope and mutability |
|---|---|
| `document_id` | Stable cloud-manifest/local logical identity; immutable. |
| `device_id` | Paired compute identity; mutable association only through future authenticated pairing/reconciliation. |
| `content_sha256` | Immutable identity of the accepted source bytes. |
| `artifact_id` | Immutable UUID for one prepared candidate; changes on every preparation/reprocessing attempt. |
| `artifact_profile_id` | Versioned, human-readable local profile name; changes only by deliberate contract revision. |
| `artifact_profile_fingerprint` | SHA-256 over canonical profile JSON; changes whenever a compatible artifact is no longer semantically valid. |
| `active_artifact_id` | Mutable catalog pointer; changes only after successful promotion. |

The initial profile is `zkd-local-artifact-v1`. Its canonical fingerprint includes, at minimum: local artifact schema version; PDF extraction/parser profile; Block 2 legal chunking contract/version; `intfloat/multilingual-e5-base`; dimension `768`; normalized embeddings; `passage: ` and `query: ` prefix semantics; token limit `512`; `block3-v1`; dense cosine metric; lexical-query strategy/version; retrieval-store schema; and hierarchy representation/bounds. It records RRF/hierarchy profiles for compatibility diagnostics, even where a runtime ranking parameter alone does not require re-embedding.

`block3-v1` is retained as the frozen embedding/index semantic component; this contract does not rename it. An artifact is compatible only when its profile fingerprint and declared required components match the running local runtime.

## 5. LocalStoreV1 decision

**Selected LocalStoreV1:** application-owned SQLite artifact databases, with SQLite FTS5 for lexical retrieval and an in-process exact cosine search over normalized `float32` embedding BLOBs. Each immutable artifact is one self-contained SQLite database; a small SQLite catalog tracks local documents, artifact pointers, durable local jobs, and manifest-outbox records.

The dense implementation is deliberately exact for V1 rather than an ANN extension. The current measured frozen corpus is modest, and exact cosine preserves the required dense Top-K ordering without a separately administered database, external service, or pre-v1 vector-extension compatibility risk. HNSW is not a local semantic requirement. Future corpus-growth measurements may justify a bundled internal ANN implementation, but only after parity testing; it must not change the retrieval contract.

| Candidate | Packaging/lifecycle | Retrieval and consistency fit | V1 decision |
|---|---|---|---|
| A. Local PostgreSQL + pgvector | Highest code reuse but introduces a server/service lifecycle, upgrades, recovery, and Windows operational burden | Native reuse of HNSW, `tsvector`/GIN, and SQL joins | Rejected: conflicts with the no-user-administered-service constraint. |
| B. SQLite + FTS5 + exact embedded cosine | One application-owned file per artifact, no server, transactional persistence, built-in full-text index, straightforward export | Preserves dense cosine Top-K, lexical retrieval, metadata filters, hierarchy traversal, and RRF with local adapters | **Selected.** |
| C. Separate embedded vector database plus metadata store | Adds runtime artifacts and multi-store consistency/recovery concerns | Requires cross-store promotion, lexical/hierarchy joins, and export coordination | Rejected: unnecessary complexity before corpus-growth evidence. |
| D. Other embedded local index | No concrete repository/product requirement beyond B | Would need to prove Windows packaging, lexical/hierarchy parity, migration, and durability | Not selected. |

SQLite FTS5 is an official full-text virtual-table facility, and SQLite transactional/journal behavior supports crash recovery when configured and used correctly. The implementation must use a bundled/validated SQLite build with FTS5 enabled and a supported journal/synchronous policy; it must not rely on an arbitrary system SQLite build. See the [SQLite FTS5 documentation](https://www.sqlite.org/fts5.html) and [SQLite transaction documentation](https://www.sqlite.org/transactional.html).

This is a design selection, not permission to add a dependency or rework current PostgreSQL code now. P2C implementation must validate 613 frozen chunks, real 768-D embeddings, document filters, hierarchy lookup, restart persistence, and retrieval parity fixtures before LocalStoreV1 is used for product data.

## 6. Required retrieval semantics

The following semantics are preserved even though PostgreSQL/pgvector, HNSW, `tsvector`, GIN, and SQL syntax are implementation details rather than local requirements.

| Required semantic | LocalStoreV1 requirement |
|---|---|
| Dense | E5 `query: ` embedding; finite normalized 768-D vector; cosine Top-K; profile/dimension/model filtering; document filtering before ranking; deterministic ties. |
| Lexical | Indexed lexical search over chunk content; safe normalized query construction; strict-first/fallback lexical behavior compatible with current Block 4 intent; document filtering before ranking; deterministic score/id ties. |
| Fusion | Application-level RRF over 1-based branch ranks, current defaults (`50`, `50`, `10`, `60`), no score-as-confidence conversion. |
| Hydration/context source | One selected-artifact bulk fetch returns chunk text, metadata, provenance, legal-unit identity, and ranks in final order. |
| Hierarchy | Bounded direct-child expansion over immutable RRF anchors; same-document/document-filter enforcement; deterministic child order; base-only fallback on lookup failure. |
| Authorization | Cloud pairing/protocol admits only the user's requested local document IDs. The local content store does not mirror cloud account/auth tables. |

FTS5 ranking need not replicate PostgreSQL `ts_rank_cd` numerically; lexical ranks, safe filtering, candidate behavior, and RRF semantics are what must be tested. Vietnamese tokenization/query fallback remains a compatibility test because multi-syllable Vietnamese terms are not magically resolved by choosing SQLite.

## 7. Logical local schema

`state/catalog.sqlite3` contains only local control metadata:

```text
local_documents(document_id, content_sha256, original_filename, mime_type,
  byte_size, source_relative_path, preparation_state, active_artifact_id,
  local_availability, created_at, updated_at, last_error_*)
artifacts(artifact_id, document_id, profile_id, profile_fingerprint,
  relative_path, state, integrity_hash, chunk_count, page_count,
  created_at, promoted_at, supersedes_artifact_id)
local_jobs(job_id, document_id, artifact_id, operation, state, attempt,
  cancellation_requested, stage, error_*, created_at, updated_at)
manifest_outbox(event_id, document_id, artifact_id, event_type, payload_metadata,
  created_at, acknowledged_at)
```

`artifact.sqlite3` contains content for exactly one immutable prepared artifact:

```text
artifact_metadata(profile_id, profile_fingerprint, source_sha256, integrity_hash, ...)
pages(page_id, page_number, raw_text, char_count)
reconstruction(normalized_text, page_offset_map, parser_profile)
legal_units(legal_unit_id, parent_unit_id, unit_type, unit_number, unit_title,
  char_start, char_end, page_start, page_end, level)
chunks(chunk_id, document_id, legal_unit_id, chunk_index, content_text,
  embedding_text, page_start, page_end, metadata_json, provenance_json)
chunk_embeddings(chunk_id, model, dimension, normalized, index_version,
  vector_float32_blob)
chunk_fts(FTS5 indexed chunk content with chunk_id mapping)
```

Foreign-key integrity, unique `(document_id, chunk_index)` and `(document_id, page_number)` constraints, profile checks, and artifact-level integrity validation are required. Content tables do not contain cloud account/session/device registry data. Device association belongs in the catalog/manifest metadata, not in each chunk.

## 8. Atomic preparation and promotion

Preparation is a two-phase local lifecycle:

```text
accepted managed source
  -> candidate artifact in <artifact_id>.staging
  -> extraction / parsing / chunking / embedding / lexical build
  -> artifact validation and integrity fingerprint
  -> same-volume atomic directory promotion to <artifact_id>
  -> short catalog transaction switches active_artifact_id
  -> READY and manifest-outbox event
```

The staging artifact contains its own SQLite database and is never queryable. Validation checks source SHA, parser/chunk/E5 profile, chunk/index cardinality, 768-D finite normalized embeddings, lexical index availability, hierarchy references, and artifact integrity before promotion.

The exact guarantee is: **no half-built candidate is ever marked READY or selected for retrieval.** If a crash happens before directory promotion, the staging directory is ignored and later cleaned. If it happens after directory promotion but before the catalog pointer transaction, the promoted directory is an unreferenced candidate and is not queryable. If the pointer transaction commits, the artifact has already been validated and exists at its immutable path. A subsequent missing file is detected as `MISSING_LOCAL_ARTIFACT`, never assumed available.

The catalog uses one writer at a time and durable SQLite transactions. Artifact databases are immutable after promotion. The runtime must preserve required journal/WAL companion files during recovery/export and must not hand-edit or rename database/journal files after a crash.

## 9. Failure, retry, and reprocessing

Failures during extraction, chunking, embedding, lexical/index creation, validation, or promotion retain the accepted source PDF, durable failure metadata, and the previous active READY artifact. A failed reprocess never destroys or replaces the previous valid artifact.

Retries are explicit, idempotent where possible, and create a new `artifact_id`. At restart, a durable local job record is reconciled: unfinished staging work is marked interrupted/failed, never resumed as READY without rebuilding or revalidating; orphan staging directories are eligible for safe cleanup; promoted-but-unreferenced artifacts are retained for diagnostic cleanup until verified unreferenced.

Reprocessing is required when source bytes differ; parser/extraction, chunking, embedding, token, index, lexical, hierarchy, or artifact-schema profile changes; integrity validation fails; or local corruption is found. Every reprocess builds a new candidate and promotes it only after validation. In-place destructive conversion is prohibited.

## 10. Queryability, deletion, and reconciliation

Content-dependent operations require all of:

```text
preparation_state = READY
compute availability = READY
local artifact availability = AVAILABLE
artifact profile = COMPATIBLE
requested capabilities = admitted
```

Any false condition disables Ask/retrieval. A cloud manifest `READY` is not enough.

For a local removal, ZKD Compute records a durable local deletion operation, prevents new jobs, removes source/artifacts after safe cancellation, marks local availability `DELETED`, and enqueues a metadata-only manifest tombstone. The cloud manifest is not an erasure mechanism for content it never held.

If a manifest deletion occurs while a device is offline, cloud records an authenticated tombstone for future reconciliation. The cloud must stop routing jobs immediately; local content remains until the paired device receives and authorizes the tombstone. Remote wipe is not claimed by V1. Device revocation likewise prevents routing but does not erase local content; users must explicitly remove it locally.

Reconciliation never fabricates availability:

| Observation | Local state/action |
|---|---|
| Manifest READY, active artifact missing | `MISSING_LOCAL_ARTIFACT`; Ask disabled; manifest update queued. |
| PDF present, active index/artifact absent | `STALE` / `NEEDS_REPROCESSING`; source retained. |
| Artifact present but profile incompatible | `STALE` / `NEEDS_REPROCESSING`; previous artifact is not queried. |
| Catalog/artifact database integrity failure | `LOCAL_STORE_CORRUPT`; quarantine affected artifact, disable queries, restore/export or reprocess. |
| Managed folder manually altered | Verify hashes/profile; mark missing/corrupt rather than guessing. |
| Device replaced | New device sees only manifest metadata; no local content is assumed present. |

## 11. Manifest sync and privacy boundary

The future `ManifestSyncClient` may send only lightweight metadata: `document_id`, filename/display alias, byte size, content-hash identifier, preparation/index state, chunk count, artifact profile/version/fingerprint, device ID, timestamps, typed errors, and local availability.

It must never send by default PDF bytes, page text, normalized text, chunks, embeddings, vector/lexical indexes, retrieved evidence, context source content, prompt context, or generated document-derived payloads. Sending any content to a `UserCloudComputeProvider` is a separate future explicit authorization/data-transfer contract.

Filename synchronization is a conscious privacy trade-off: names may expose sensitive legal matter information. V1 permits it only because an offline document list is a product requirement; future work should offer a user-controlled display alias/filename privacy option. The manifest must not be described as free of sensitive metadata.

## 12. Backup/export and model artifacts

Platform manifest backup protects lightweight metadata only; it is not a backup of local documents or indexes. A future user-initiated local export/import package must include managed source PDFs, catalog metadata, selected prepared artifacts or sufficient rebuild inputs, artifact profiles/fingerprints, and integrity hashes. It must include SQLite journal/WAL companions when applicable or use a verified SQLite backup procedure. Export/import implementation is deferred.

E5 is a local runtime asset under `models/huggingface/hub/`, never copied into a document directory. It is restart-safe, profile/revision-aware, integrity-validated before use with the existing canonical E5 artifact-validation semantics, and loaded from a managed cache. The canonical model remains `intfloat/multilingual-e5-base`; model artifacts are not downloaded unpredictably on every job. Installer/update distribution remains a later decision.

## 13. Runtime resource and job lifecycle

ZKD Compute starts a lightweight internal control process. With no job, E5/index resources may remain unloaded. On prepare/query, the runtime loads only required internal components, performs admission, records durable local job state, and reports product-level status. An idle policy may unload expensive resources later; the user never starts or stops internal services manually.

Redis/RQ is a **replaceable orchestration implementation detail**, not a local semantic dependency. Local V1 still needs durable job ownership, one-writer/document admission, queued work, retry attempt records, cancellation, restart reconciliation, stage/status updates, and typed failure reporting. `local_jobs` plus an internally managed desktop scheduler/worker boundary is the planned replacement. No local Redis server is required.

MinIO/S3 is likewise an implementation detail. Its semantic roles—managed durable source PDF, content hash/deduplication, atomic ownership, artifact lookup, and deletion—map to the managed source path, catalog, and immutable artifact directories. Local V1 requires no MinIO service. Current backend MinIO/RQ code remains unchanged until local adapters are implemented and verified.

## 14. Blocks 1–6 localization map

| Block | Semantic contract preserved | Local V1 ownership/adapter change |
|---|---|---|
| Block 1 | Yes: validation, hash, dedupe, lifecycle intent | `DocumentStore` accepts paired local content and persists managed source; transport/storage replace platform API/MinIO/RQ handoff. |
| Block 2 | Yes: parser, reconstruction, legal units, chunking, provenance | Reuse domain processing in ZKD Compute; `ArtifactStore` persists candidate artifact instead of PostgreSQL rows. |
| Block 3 | Yes: canonical E5, passage prefix, normalized 768-D vectors, 512-token input contract, `block3-v1` semantics | `LocalRetrievalStore` persists float32 vectors/FTS metadata; PostgreSQL HNSW/GIN implementation replaced. |
| Block 4 | Yes: query prefix, dense/lexical branch behavior, document filter before ranking, RRF, hydration, hierarchy rules | Local repository adapter executes exact cosine, FTS5, and local hierarchy lookups; no cloud database. |
| Block 5 | Yes: deterministic selection, token counting, evidence formatting | Runs unchanged in Compute against hydrated local candidates. |
| Block 6 | Yes: grounding, answerability status, citation/provenance semantics | Runs in Compute through a future local or explicitly user-funded provider adapter; no platform content transfer/fallback. |

## 15. Required adapter boundaries and P2C.3 handoff

The current repository demonstrates real infrastructure coupling at upload/MinIO/RQ, SQLAlchemy retrieval/hierarchy repositories, and worker entry points. Future implementation should introduce only these concrete boundaries:

| Boundary | Purpose |
|---|---|
| `DocumentStore` | Managed source acceptance, dedupe, source lookup, local deletion. |
| `ArtifactStore` | Candidate artifact staging, validation, immutable promotion, catalog active pointer, integrity checks. |
| `LocalRetrievalStore` | Dense/lexical/hierarchy query and bulk hydration over an active local artifact. |
| `LocalJobStore` | Durable local preparation/query job state, cancellation, retry, and restart reconciliation. |
| `ManifestSyncClient` | Metadata-only outbox/tombstone synchronization; never document content. |
| `ComputeRuntime` | Lifecycle/admission boundary that owns components and exposes product operations. |

P2C.3 needs, but must not yet implement, authenticated conceptual operations: `accept_document`, `prepare_document`, `get_document_state`, `query_document_set`, `cancel_job`, `delete_document`, capability reporting, artifact availability reporting, and manifest-outbox acknowledgement. It must bind each to paired user/device authorization, non-content IDs, and the local-state contracts above.

## 16. Open decisions after this contract

1. Browser-to-ZKD Compute transport, loopback/origin posture, and pairing/security protocol.
2. Desktop framework, installer/updater, code signing, autostart, model delivery, and runtime containment.
3. Manifest synchronization protocol, conflict/tombstone delivery, and export/import UX.
4. UserCloudComputeProvider credential custody, user consent, and content/evidence transfer boundary.
5. Local-store implementation acceptance thresholds for larger corpora and any future bundled ANN upgrade.

---

```text
LOCAL_DATA_RUNTIME_CONTRACT_V1
STATUS: ACTIVE V1 LOCAL DATA/RUNTIME CONTRACT
```
