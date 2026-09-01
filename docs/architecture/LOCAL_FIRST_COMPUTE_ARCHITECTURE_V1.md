# LOCAL_FIRST_COMPUTE_ARCHITECTURE_V1

**Project:** ZKD / Vietnamese Legal RAG
**Status:** **ACTIVE V1 ARCHITECTURE CORRECTION**
**Decision date:** 2026-09-01
**Scope:** Product ownership and runtime boundary for a local-first, near-zero-platform-compute V1
**Supersedes for active V1:** the always-on DigitalOcean execution topology and provider map
**Preserves:** semantic contracts of Blocks 1–6 until each workload has a tested local replacement

---

## 1. Purpose and precedence

This document corrects the active product direction. It is deliberately a new document: `HYBRID_RUNTIME_CONTRACT_V1.md`, `CLOUD_INFRASTRUCTURE_TOPOLOGY_V1.md`, and `CLOUD_PROVIDER_SELECTION_V1.md` remain immutable historical records.

For active V1, this document governs product data ownership and compute placement where it differs from those older cloud-first documents. In particular, the historical always-on DigitalOcean App Node, Worker Node, Managed PostgreSQL, Spaces, platform E5 runtime, platform retrieval, and platform document processing plan is **SUPERSEDED_FOR_ACTIVE_V1**. It is retained only as a possible future `PlatformCloudComputeProvider` design, subject to new human approval.

This is an architecture decision, not an implementation claim. The existing backend continues to serve development/testing until the replacement path passes its later design and verification gates.

## 2. Product invariants and cost boundary

1. The public web shell remains online independently of a user's compute device.
2. The platform must not pay for heavy user compute by default.
3. Platform-funded PDF processing, chunking, E5 embedding, indexing, query embedding, vector/lexical retrieval, RRF, hierarchy retrieval, context construction, and LLM generation are out of scope for active V1.
4. A new PDF is accepted only after a capable `ComputeProvider` is `READY`. The platform must never accept the PDF and silently process it in platform cloud infrastructure later.
5. The raw PDF path for local compute is Browser -> secure local transport -> ZKD Compute -> application-owned local data directory. It does not traverse the platform backend or platform object storage by default.
6. Platform cloud does not store user PDF bytes, page text, chunk bodies, embeddings, vector-index payloads, or retrieved document content by default.
7. `LocalComputeProvider` uses the user's own machine. `UserCloudComputeProvider` is separately configured and paid for by that user. Neither is a platform-funded fallback.
8. No automatic move of document content or jobs to another provider is allowed. A user must explicitly configure and authorize a `UserCloudComputeProvider` before any such transfer.
9. `PlatformCloudComputeProvider` is future-only. Introducing it requires a separately approved product tier, data contract, cost model, and architecture decision.

The target is near-zero platform baseline compute cost. It does not promise that every identity, static-hosting, or control-metadata service is permanently free; it rejects mandatory always-on heavy compute and platform growth in document storage for normal user workloads.

## 3. Always-on web shell and control metadata

The always-online platform is a lightweight web/control shell. It may provide static/frontend delivery, authentication, account metadata, device/provider registry, pairing and revocation metadata, presence/status, document manifests, job/status metadata, and configuration metadata.

It must remain usable without a GPU, E5 runtime, vector database, LLM, PDF worker, local database, or local document content. With no compute provider connected, a user can authenticate, navigate, inspect document manifests and prior status/errors, see chunk/index counts from a prior successful run, manage settings, and connect or disconnect a provider.

The shell must not represent metadata visibility as content availability. It stores no authority to answer from a locally held document while its compatible compute is unavailable.

## 4. PDF ingestion gate and local data path

### Provider offline

When no provider with `pdf_processing`, `chunking`, `embedding`, and `indexing` capability is `READY`:

- Upload is disabled before a file is accepted.
- The UI explains: **“Connect a compute provider to upload and prepare documents.”**
- No raw PDF is sent to the platform API, object store, Redis/RQ queue, or a delayed processing queue.

### Provider ready

When a provider with the required preparation capabilities is `READY`:

- the UI may enable file selection and submit the file only to the selected provider's approved transport;
- LocalComputeProvider receives the PDF over a future secure browser-to-local channel and persists it under its application-owned local data directory;
- preparation lifecycle updates may be synchronized as lightweight manifest metadata only;
- a failure must be reported as a product-level preparation failure, not rerouted to platform compute.

The exact browser/local transport is deferred. Candidate transports include loopback HTTPS, loopback WebSocket, a native app protocol/deep link, or another companion mechanism. No transport is selected here.

## 5. ComputeProvider model, lifecycle, and capabilities

The product exposes one high-level `ComputeProvider` abstraction.

| Provider | Ownership and billing | Active V1 role |
|---|---|---|
| `LocalComputeProvider` | User's own ZKD Compute installation and hardware | Primary document preparation, local RAG, and optionally local generation |
| `UserCloudComputeProvider` | User's own external account, credentials, data authorization, and provider bill | Later explicit alternative/fallback; no provider/vendor is selected here |
| `PlatformCloudComputeProvider` | Platform-funded | Explicitly out of scope for active V1 |

Provider state is distinct from document preparation state. Compatible lifecycle vocabulary is `OFFLINE`, `CONNECTING`, `AUTHENTICATING`, `READY`, `BUSY`, and `UNAVAILABLE`; a future implementation may retain the frozen contract's `IDLE` and `DRAINING` states. Connectivity alone never makes a provider ready.

Capabilities must be explicit and admitted per job, not inferred from online state or hardware name. Initial conceptual capabilities are:

```text
pdf_processing, chunking, embedding, indexing, retrieval, generation
```

A device can be ready for CPU document preparation/retrieval but unavailable for local generation. Upload requires preparation capabilities; Ask requires the capabilities necessary to access the selected document and perform the requested retrieval/generation path.

ZKD Compute is a future installed companion, not developer-operated infrastructure: install and pair once, optionally enable autostart, reconnect automatically, report `READY`/`OFFLINE`/`BUSY`, load approved runtime/model artifacts on demand, and unload expensive models after an idle policy. Normal UX never asks users to run Docker, Python, pip, worker scripts, Redis commands, or an Ollama command.

## 6. Local data ownership and cloud manifest boundary

Local ZKD Compute owns raw PDFs, extracted page text, legal structure, chunks, passage embeddings, dense/lexical/hierarchy indexes, retrieval evidence, and local context artifacts. These persist in an application-owned local data directory, not arbitrary working folders, the Git repository, temporary browser storage, or user-chosen scratch paths. Exact desktop storage implementation is a later decision.

The cloud may retain a lightweight synchronized document manifest so the web shell is useful offline:

```text
document_id, user_id, filename, file_size, created_at, updated_at,
preparation_state, chunk_count, index_status, last_successful_processing_at,
compute_provider_id, error_code, error_message, local_artifact_id,
local_artifact_version, local_artifact_hash, document_availability_state
```

The manifest must never include PDF bytes, page text, chunk content, embeddings, vector index payloads, legal document body content, or retrieved document content. `document_id` is the cloud-visible identity; `local_artifact_id`, content hash, and artifact version bind it to a particular local installation without transferring content.

Reconciliation is future work and must cover local deletion, device replacement, reprocessing, stale manifest records, and a manifest claiming `READY` when the local artifact is missing. The cloud may record availability and error state but must not reconstruct the missing content itself.

## 7. Document lifecycle, offline behavior, and multi-device semantics

User-facing preparation states are `PREPARING`, `READY`, `FAILED`, and `STALE`. `WAITING_FOR_COMPUTE` is reserved for meaningful historical/reprocessing/disconnected-authorized workflows; it is not a reason to accept a brand-new upload while no provider is ready. Internal processing/chunking/indexing progress may remain more granular.

`PREPARATION_STATE=READY` means a successful artifact was previously prepared. It does **not** mean the document is queryable now. `COMPUTE_AVAILABILITY` is separately reported. For example:

```text
Document: READY (121 chunks, indexed, last processed timestamp)
Compute:  OFFLINE
Result:   manifest view is available; retrieval and Ask are unavailable
```

A document prepared on Device A remains local to Device A. Device B must not claim local availability merely because it can view the manifest. Device B obtains content only through a future explicit transfer or re-preparation flow; V1 implements no automatic content synchronization.

The web contract is therefore:

| State | Web behavior |
|---|---|
| Compute offline | Website and manifests work; Upload/Ask for local-only content disabled; connect CTA shown |
| Compute ready | Upload and preparation enabled; Ask enabled only for locally available ready documents and requested capabilities |
| Compute busy | Product state shown; jobs only follow a future explicit queue/admission protocol |
| Preparation failed | Human-readable product error; never a raw runtime exception |

## 8. Local compute responsibilities and Core RAG reuse audit

The local runtime is responsible for PDF parsing, text extraction, legal structure analysis, chunking, E5 passage/query embedding, local indexing, dense/lexical/RRF/hierarchy retrieval, context construction, and generation when a local LLM is selected. Local RAG plus a user-funded cloud generation provider remains an allowed future composition, but its data boundary and consent must be explicit.

| Current component | Classification | Migration implication |
|---|---|---|
| Block 1 PDF validation/ingestion | **B — REUSABLE_WITH_TRANSPORT/OWNERSHIP_CHANGE** | Preserve validation/hash/lifecycle semantics; replace platform upload/object handoff with the local provider admission and artifact path. |
| Block 2 parsing, reconstruction, legal chunking | **A — REUSABLE_AS_IS** | Reuse semantic processing/chunking rules inside ZKD Compute; package/runtime boundary changes. |
| Block 3 E5 artifact validation and E5 embedder | **B — REUSABLE_WITH_TRANSPORT/OWNERSHIP_CHANGE** | Keep approved `intfloat/multilingual-e5-base` and integrity rules; provision/model-cache it locally, not on a platform app node. |
| Block 3 PostgreSQL/pgvector index persistence | **C — CLOUD-SPECIFIC_AND_MUST_MOVE** | Current SQLAlchemy/PostgreSQL canonical storage is not an active-V1 local-first ownership model; choose local persistence before porting. |
| Block 4 dense retrieval, lexical retrieval, RRF | **B — REUSABLE_WITH_TRANSPORT/OWNERSHIP_CHANGE** | Preserve query, ranking, filtering, lexical, RRF, and hierarchy semantics; repository/database adapter must become local. |
| Block 4 hierarchy retrieval | **B — REUSABLE_WITH_TRANSPORT/OWNERSHIP_CHANGE** | Preserve bounded anchor/child behavior; relocate hierarchy queries with the chosen local store. |
| Block 5 deterministic context construction | **A — REUSABLE_AS_IS** | Pure deterministic selection/formatting semantics can run in ZKD Compute. |
| Block 6 `AnswerService`, answerability/citation semantics | **B — REUSABLE_WITH_TRANSPORT/OWNERSHIP_CHANGE** | Preserve status/citation/provenance semantics; provider dispatch and evidence ownership move into compute. |
| `LLMClient`/provider abstraction | **B — REUSABLE_WITH_TRANSPORT/OWNERSHIP_CHANGE** | Existing protocol is a useful interface; add explicit local/user-cloud provider consent and data-boundary behavior later. |
| Redis/RQ orchestration and workers | **C — CLOUD-SPECIFIC_AND_MUST_MOVE** | Current queues execute platform workers and cannot accept local-only PDFs; define device-aware local scheduling/protocol. |
| MinIO/S3 storage client | **C — CLOUD-SPECIFIC_AND_MUST_MOVE** | Existing raw-PDF cloud storage is prohibited by default. Replace with local artifact storage adapter. |
| Document lifecycle/database models and repositories | **D — NEEDS_NEW_IMPLEMENTATION** | Split lightweight cloud manifest/control metadata from local artifact lifecycle; define synchronization and ownership protocol. |

This classification is not permission to change Blocks 1–6 now. Semantic compatibility tests must precede every replacement.

## 9. Local persistence and index-store decision (open)

No local store is selected in this phase. The future local data/runtime contract must compare at least:

| Option | Strengths | Material questions |
|---|---|---|
| Local PostgreSQL + pgvector | Highest reuse of current SQL, HNSW, GIN, and hierarchy queries | User-friendly Windows installation, service lifecycle, memory/disk footprint, backup UX |
| Embedded vector store/database | Potentially simple companion packaging | Equivalent lexical search, metadata/hierarchy query expressiveness, export/migration, deterministic ranking parity |
| SQLite plus compatible vector extension | Small footprint and conventional local file backup | Windows packaging, vector/HNSW behavior, full-text Vietnamese semantics, concurrency and migration support |
| Another embedded local index | Potentially optimized retrieval footprint | Durable metadata transactions, lexical/hierarchy parity, backup/export, versioned migrations, and long-term support |

Selection criteria are Windows-friendly installation, reliable persistence, dense and lexical retrieval parity, metadata/hierarchy query support, backup/export, migration path, resource footprint, and auditability. Trend popularity is not a selection criterion.

## 10. Browser-to-ZKD Compute security boundary

The final transport/security review must require: authenticated paired browser/account; short-lived pairing/session credentials; strict origin and CSRF checks; loopback-origin restrictions if loopback is selected; allowlisted versioned protocol messages; explicit browser file-selection authorization; job ownership and document/provider authorization; device revocation; path traversal prevention; no arbitrary command execution; least-privilege local filesystem scope; encrypted authenticated traffic where transport permits; and safe handling of reconnects/cancellation.

The companion must never treat a browser message as authority to execute shell commands, install arbitrary packages, access arbitrary filesystem paths, or operate another user's document. A UserCloudComputeProvider additionally requires an explicit content-transfer consent/data contract before evidence or document material leaves the local runtime.

## 11. Superseded DigitalOcean plan and Terraform safety

`CLOUD_INFRASTRUCTURE_TOPOLOGY_V1.md`, `CLOUD_PROVIDER_SELECTION_V1.md`, `STAGING_PROVISIONING_RUNBOOK_V1.md`, and `deployment/terraform/staging/` remain historical reference material only. For active V1 they are **SUPERSEDED_FOR_ACTIVE_V1**. The following require a fresh explicit human decision and are not authorized by this architecture:

- `terraform apply` in `deployment/terraform/staging/`;
- a DigitalOcean App Node or Worker Node;
- DigitalOcean Managed PostgreSQL or Spaces;
- Cloudflare staging resources, DNS changes, or a canonical-data migration.

No Terraform resource is deleted or changed by this document. No provisioning, migration, DNS, or Cloudflare operation occurred while adopting this correction.

## 12. Safe migration plan

1. **Architecture freeze:** adopt this correction and preserve existing system paths for development/testing.
2. **Local data/runtime contract:** choose local persistence, artifact layout, backups/export, retention, manifest schema boundary, and reconciliation semantics.
3. **Browser ↔ ZKD Compute protocol:** define transport, pairing, capability admission, request lifecycle, revocation, and local security tests.
4. **ZKD Compute MVP:** build a user-installable, paired, autostart-capable companion without developer tooling.
5. **Local preparation:** move PDF validation, parsing, chunking, E5 passage embedding, and local index creation behind compatibility tests.
6. **Local retrieval/context:** port the repository adapter and run Blocks 4–5 semantics locally, including dense, lexical, RRF, hierarchy, and deterministic context tests.
7. **Generation routing:** support local generation and explicitly user-funded cloud generation while preserving structured answerability/citation behavior and no-silent-fallback rules.
8. **Minimal shell:** reduce the cloud backend to metadata/control responsibilities only after local replacements and migration/reconciliation tests pass.

Existing cloud-oriented development and recovery paths must not be destructively removed until their tested replacements are accepted. No document content migration to a platform cloud target is part of this plan.

## 13. Unresolved decisions

1. Local persistence/index database and Windows packaging strategy.
2. Secure Browser ↔ ZKD Compute transport and local-origin policy.
3. Desktop companion framework, installer/updater, autostart, runtime/model distribution, and resource admission UX.
4. Manifest synchronization, local-artifact reconciliation, deletion/device replacement, backup/export, and stale-state semantics.
5. `UserCloudComputeProvider` credential custody, document/evidence transfer consent, storage location, provider-specific privacy boundary, and revocation.
6. Device/provider job protocol, scheduling, cancellation, and offline/busy behavior for preparation and retrieval workloads.
7. Compatibility-verification matrix needed to preserve Blocks 1–6 semantics on the selected local store.

---

```text
LOCAL_FIRST_COMPUTE_ARCHITECTURE_V1
STATUS: ACTIVE V1 ARCHITECTURE CORRECTION
```
