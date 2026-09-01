# CLOUD_INFRASTRUCTURE_TOPOLOGY_V1

**Project:** ZKD / Vietnamese Legal RAG
**Status:** **FROZEN V1 TOPOLOGY**
**Phase:** Hybrid Migration P2B.1
**Scope:** Vendor-neutral, initial always-online cloud control plane
**Contract dependency:** `HYBRID_RUNTIME_CONTRACT_V1` SHA-256 `d1a51bea4355ecf303bd08094bc356cee42dc670e6c792788d7b24a78fbde085`
**Evidence dependency:** P2A final capacity measurement

---

## 1. Scope and non-goals

This document freezes *what* the initial cloud control plane requires, not which provider supplies it. It makes no vendor selection, purchase, DNS, Cloudflare, deployment, data-migration, schema, or application-behavior change.

The cloud control plane owns authentication, canonical PostgreSQL state and pgvector indexes, document lifecycle metadata, S3-compatible object coordination, E5 query embedding, retrieval (dense, lexical, RRF, and hierarchy retrieval), deterministic context construction, citation contracts, device/provider registry and future routing/job metadata.

Blocks 1–6 retain their existing behavior. The Hybrid Runtime Contract remains authoritative for future device/provider behavior.

### Product cost boundary

Platform-funded LLM inference is **out of scope** for V1. This topology does not size, provision, select, or price Qwen, GPU servers, centralized cloud LLMs, platform LLM credits, subscriptions, or billing.

Future generation providers are separate user-funded compute:

- `LocalDeviceProvider`: a user's own CPU/GPU through ZKD Compute;
- `UserCloudProvider`: that user's own provider account/credential and billing relationship;
- `PlatformCloudProvider`: future only, not required by V1.

The control plane must remain useful with all personal devices offline. Generation capacity is not a sizing input in this document.

---

## 2. P2A evidence consumed

P2A used an isolated frozen corpus of 44 documents, 613 chunks, 613 vector indexes, and 18 objects. No generation call was included.

| Measurement | Result |
|---|---:|
| 1-user retrieval | median 72.6 ms; P95 87.8 ms; 13.45 req/s |
| 5-user retrieval | median 318.5 ms; P95 370.9 ms; 15.44 req/s |
| 10-user retrieval | median 598.3 ms; P95 679.8 ms; 16.44 req/s |
| 5 users + indexing | median 562.8 ms; P95 713.1 ms; 8.63 req/s |
| 5 users + processing | median 311.6 ms; P95 355.2 ms; 15.80 req/s |
| App-node projected peak when workers are split | about 2.5 GiB |
| Full application/worker colocation projected peak | about 5.9 GiB |
| Indexing worker | 613 chunks / 39 batches / 100.2 s / 6.12 chunks/s; 2.06 GiB peak RSS; about 8 host Docker CPUs observed |
| Processing worker | 1.26 GiB peak RSS; CPU materially below indexing under the measured workload |
| Database | about 16 MiB total; HNSW about 2.4 MiB; GIN about 696 KiB |
| Redis | about 1.28 MiB used memory in the measured state |
| App/runtime artifacts | API image about 2.93 GiB; E5 cache about 1.1 GiB |

These are local, isolated benchmark observations, not a cloud performance promise. E5 query work is serialized by the shared model instance, which preserved correctness during the test but constrained concurrent-request latency.

---

## 3. Initial vendor-neutral topology

```text
                         PUBLIC
    User Browser ── HTTPS ──> Cloudflare ingress / DNS / TLS / WAF / CDN
                                      |
                                      | authenticated same-origin traffic
                                      v
              +------------------------------------------------+
              | APP NODE — PRIVATE ORIGIN                      |
              | FastAPI, E5 query embedding, retrieval,        |
              | context/citation contracts, frontend/nginx,     |
              | small control-plane processes                   |
              | Redis initially colocated (operational state)   |
              +-------+------------------+---------------------+
                      |                  |                 |
             private DB traffic    private object API   private Redis
                      |                  |                 |
                      v                  v                 v
        CANONICAL: Managed PostgreSQL   CANONICAL:      OPERATIONAL:
        + pgvector                       S3-compatible   Redis / RQ / rate
        metadata, chunks, indexes,       object storage  limits / leases
        auth, lifecycle, provenance      source PDFs

              +------------------------------------------------+
              | WORKER NODE — PRIVATE                          |
              | indexing worker; processing worker;             |
              | general lifecycle/background workers            |
              +-------+------------------+---------------------+
                      |                  |                 |
                      +-- private access to PostgreSQL, object storage, Redis

    USER-FUNDED COMPUTE, FUTURE AND OUTSIDE PLATFORM SIZING
    User-owned ZKD Compute / LocalDeviceProvider  <-->  control-plane protocol
    User-owned external account / UserCloudProvider <--> control-plane protocol
```

Cloudflare remains the current public ingress, TLS, DNS, WAF/CDN boundary. A Cloudflare Tunnel remains appropriate for a first cloud deployment when it avoids opening a public origin and preserves the existing same-origin routing pattern. A later direct origin behind Cloudflare proxying is an allowed operational evolution after origin TLS, firewall, private-network, and health-check decisions; it is not a prerequisite for this topology.

---

## 4. Capacity contracts

### 4.1 App node

**Initial target:** `SIZE_M = 4 vCPU / 8 GiB RAM / 40 GiB preferred system disk`
**Classification:** `SIZE_M_MARGINAL`

The measured split-app projection is about 2.5 GiB. This permits the initial control-plane roles but does not justify unrestricted worker colocation. Sustained E5 indexing must not run on this node by default. The 10-user local benchmark was stable, but cloud CPU, network, storage, and process scheduling behavior are unknown.

Monitor CPU, memory pressure/OOM events, request queueing, retrieval errors, and per-stage timings. Investigate sustained P95 retrieval materially above the measured 5-user reference (370.9 ms) under comparable no-indexing load. Resize or split before routinely operating at or beyond the measured 10-user P95 reference (679.8 ms), or immediately on persistent queueing, memory pressure, or non-zero correctness/safety errors. These are evidence-based operational triggers, not customer-facing SLOs.

First response to pressure is vertical resize. Next is multiple API replicas and, only if measurement requires it, a separately scalable embedding architecture. No scaling mechanism is introduced by this document.

### 4.2 Worker node

**Initial target:** `4 vCPU / 6 GiB RAM / 40 GiB system and artifact disk`.

This is conservative but evidence-based: indexing consumed 2.06 GiB peak RSS and high CPU; processing consumed 1.26 GiB peak RSS; the general worker has a 1 GiB Compose limit. Six GiB leaves runtime/model-cache and operating headroom without assuming an unsupported 8 GiB minimum.

CPU, not RAM, is the expected first constraint for indexing. Operate one indexing worker at a time initially. Processing and general/lifecycle workers may share the worker node while indexing is idle or demonstrably light; they must not be treated as unrestricted peers of sustained indexing. If queue age grows or indexing competes with document processing, first resize or add worker capacity rather than competing with the API node.

### 4.3 Managed PostgreSQL

PostgreSQL is canonical and must be PostgreSQL-compatible with the required pgvector extension/operator support, secure private connectivity, backup/restore capability, sufficient connections, and an upgrade path.

| Class | Recommendation |
|---|---|
| Minimum viable initial | 1 vCPU / 2 GiB RAM / 20 GiB persistent storage, only where the provider supports the required PostgreSQL and pgvector capabilities |
| Preferred initial | 2 vCPU / 4 GiB RAM / 25 GiB persistent storage |

The corpus is currently tiny (about 16 MiB database, 2.4 MiB HNSW, 696 KiB GIN) and observed connections were low, so copying the app-node size to PostgreSQL would not be evidence-based. Upgrade on sustained database CPU/memory pressure, connection wait/exhaustion, I/O latency affecting retrieval, restore/backup limitations, or material corpus/index growth. Provider selection must verify pgvector compatibility before migration.

### 4.4 Object storage and app disk

Use private, durable, S3-compatible object storage with an isolated bucket per environment. It stores source PDFs and applicable artifacts; its capacity is not counted as app-node disk. Require least-privilege credentials, lifecycle capability, durable backup expectations, and acceptable egress characteristics.

App-node disk is **25 GiB minimum / 40 GiB preferred**. The evidence includes a 2.93 GiB API image, 1.1 GiB E5 artifact cache, container/runtime overhead, logs, and temporary workload. Operational deployment must provide log rotation and image cleanup; model artifacts are deployment-provisioned and integrity-checked, not user-selected at runtime.

### 4.5 Redis placement

**Decision:** colocate Redis on the initial App Node with persistent local storage and private network access.

This is justified by the measured 1.28 MiB Redis footprint and avoids premature managed-service complexity. Redis is nevertheless operationally significant: it carries RQ queues/results, rate-limit state, and active-generation leases. It is not canonical business truth—the document lifecycle and deletion records live in PostgreSQL—but it is not safely describable as disposable.

Existing reconciliation/recovery logic accounts for stale RQ state and the Deployment + Backup + Recovery verification includes Redis-loss recovery. A Redis failure can interrupt queue admission, rate limits, leases, and work execution until recovery/reconciliation completes. Move Redis to a separate or managed placement when App Node memory/CPU/isolation needs, HA expectations, queue pressure, or operational recovery evidence warrant it.

---

## 5. Network and trust boundaries

| Boundary | Required posture |
|---|---|
| Public ingress | Only HTTPS through the configured ingress boundary. Browser traffic reaches the same-origin frontend/API path. |
| App origin | Private where feasible; ingress connector/proxy is the only public-facing path. Runtime secrets are injected, never committed. |
| PostgreSQL | No unnecessary public exposure. App and worker private network access only; credentials scoped to application needs. |
| Redis | No public exposure. App and workers private network access only. |
| Object storage | Private endpoint/credentials where provider supports it; bucket access limited to required service identities. |
| Worker node | No browser-facing endpoint. Private access only to PostgreSQL, Redis, object storage, and required runtime artifacts. |
| Future device/provider credentials | Isolated from frontend delivery and never grant database/admin/other-user access. |

TLS terminates at the public ingress and is preserved/controlled appropriately to the origin. The precise ingress/origin TLS arrangement is provider-specific and deferred.

---

## 6. Failure domains and recovery boundaries

| Failure domain | Effect | Preserved state / allowed recovery statement |
|---|---|---|
| App Node | Browser API, auth, retrieval, and control-plane requests unavailable | Canonical PostgreSQL and object state survive; replace/restart app from artifacts and configuration. |
| Worker Node | Ingestion/processing/indexing/lifecycle work delayed | Canonical data is not destroyed by worker loss; lifecycle records and retry/reconciliation contracts determine safe recovery. |
| PostgreSQL | Canonical relational/vector state unavailable | Service operations depending on canonical state stop; restore is a database recovery operation. |
| Redis | RQ work, rate limits, and leases disrupted | Redis is operational state, not canonical truth. Use existing recovery/reconciliation behavior; do not claim loss is consequence-free. |
| Object storage | Original-document access, ingestion, and related lifecycle work unavailable | PostgreSQL metadata remains but cross-store consistency must be checked; paired backup/restore protects canonical object references. |
| Cloudflare ingress | Public product access unavailable | Private components may remain running, but this topology does not claim automatic ingress failover. |

Canonical backup boundary: **PostgreSQL and object storage together**. The existing recovery evidence verifies paired backup/checksum/reconciliation, cross-store restore, HNSW rebuild behavior, Redis-loss recovery, and immutable backup checks. Redis persistence/recovery remains operationally required; it is not a substitute for canonical PostgreSQL/object backups. E5 cache/runtime artifacts are reproducibly provisioned artifacts, not canonical corpus state.

---

## 7. Environment separation

Initial environments are `staging.zkd.id.vn` and production. They must have separate:

- PostgreSQL databases/instances and credentials;
- Redis state and credentials;
- object-storage buckets and credentials;
- application/runtime secrets, release identities, and logs;
- worker deployments and queue state.

Production and staging must never present divergent canonical state behind the same Cloudflare production hostname. No hostname, bucket, secret, or environment is created by this document.

---

## 8. Portability and remaining couplings

The runtime is provider-portable at the configuration boundary:

- `DATABASE_URL` supplies database connectivity;
- `REDIS_URL` supplies Redis connectivity;
- `MINIO_ENDPOINT`, credentials, bucket, and `MINIO_SECURE` express S3-compatible storage configuration;
- `DEPLOYMENT_PROFILE` is topology-oriented and profiles include `cloud_control_plane`;
- `EMBEDDING_MODEL_CACHE_DIR` identifies a deployment-provisioned E5 artifact boundary;
- future generation is abstracted by the frozen `GenerationProvider` concept, without selecting a vendor here.

Known operational couplings are acceptable but must be checked during provider selection:

1. PostgreSQL must support the project-required pgvector version/features and HNSW/GIN behavior.
2. Object storage must be S3-compatible with the present MinIO client semantics, private endpoint/credential model, bucket operations, and recovery tooling.
3. Docker Compose remains the current packaging/operations format; it is not itself a cloud-vendor lock-in.
4. Current Cloudflare Tunnel configuration is vendor-specific ingress packaging, isolated to the ingress overlay; the logical topology remains usable with another approved ingress boundary.
5. E5 cache persistence and offline artifact provisioning must be available to both API and indexing workloads according to the selected placement.

No runtime portability blocker was identified in this audit.

---

## 9. Security baseline

- inject secrets through the selected runtime secret mechanism; never commit credentials;
- use TLS at public ingress and protect origin traffic appropriately;
- keep PostgreSQL and Redis private where available;
- issue least-privilege object-store credentials and environment-separated buckets;
- grant workers only the data/service access they require;
- isolate future device/provider credentials from frontend assets and prohibit their use as database/admin credentials;
- retain existing authentication, authorization, lifecycle, citation, and audit behavior unchanged.

This is a V1 infrastructure baseline, not an enterprise security-program claim.

---

## 10. Scaling path

1. **App pressure:** vertically resize the App Node; then add API replicas and revisit embedding placement only after measurement.
2. **Worker pressure:** resize the Worker Node or add worker capacity; preserve the indexing CPU isolation rule.
3. **PostgreSQL growth:** use the managed-database resize/connection/storage path after observing the defined database triggers.
4. **Object growth:** scale external object storage independently of app-node disk.
5. **Generation:** LocalDeviceProvider and UserCloudProvider are separate user-funded compute paths; they do not consume platform LLM/GPU capacity in this V1 topology.

No autoscaling, HA, broker replacement, or deployment mechanism is implemented or implied by this document.

---

## 11. Provider-specific decisions deliberately deferred

- cloud/VPS, managed PostgreSQL, object-storage, and Redis provider selection;
- exact VM/database classes, regions, networking, private-link, and backup-retention products;
- Cloudflare Tunnel versus direct proxied origin after operational security review;
- ingress/origin TLS and firewall implementation details;
- monitoring/logging provider and alert routing;
- exact managed PostgreSQL pgvector version/support verification;
- object-storage durability/egress/lifecycle terms and migration plan;
- deployment automation, DNS, data migration, and environment creation;
- all LLM vendor, GPU, central inference, credits, billing, and BYOK connection decisions.

---

## 12. Freeze statement

This document freezes the initial vendor-neutral control-plane topology and measured capacity contracts. It does not amend `HYBRID_RUNTIME_CONTRACT_V1`, Blocks 1–6, generation funding, or user/provider semantics.

```text
CLOUD_INFRASTRUCTURE_TOPOLOGY_V1
STATUS: FROZEN V1 TOPOLOGY
```
