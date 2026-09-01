# CLOUD_PROVIDER_SELECTION_V1

**Project:** ZKD / Vietnamese Legal RAG
**Status:** **FROZEN V1 PROVIDER MAP**
**Decision date:** 2026-09-01
**Topology dependency:** `CLOUD_INFRASTRUCTURE_TOPOLOGY_V1` SHA-256 `b69a5a0cd4055b60aa54a1a9a2fb129f9902e0c60bfd67a2cae7a87f38bdefc4`
**Runtime-contract dependency:** `HYBRID_RUNTIME_CONTRACT_V1` SHA-256 `d1a51bea4355ecf303bd08094bc356cee42dc670e6c792788d7b24a78fbde085`

---

## 1. Scope and decision

This document maps the frozen vendor-neutral topology to an initial provider. It does **not** provision resources, create a VPC, change DNS or Cloudflare, deploy an environment, migrate data, or change application behavior.

**Selected provider:** DigitalOcean
**Primary region:** Singapore (`SGP1`)
**External ingress:** Cloudflare DNS, TLS, and Tunnel

The platform control plane remains cloud-canonical. Blocks 1–6 retain their behavior. No DigitalOcean SDK, API, or provisioning logic belongs in application/domain code.

### Product cost invariant

This map excludes all platform-funded LLM inference. It does not select, size, buy, or price Qwen, GPU instances, centralized LLM inference, platform credits, subscriptions, billing, or a cloud LLM vendor.

Future generation is separate user-funded compute:

- `LocalDeviceProvider`: user's own ZKD Compute device;
- `UserCloudProvider`: user's own connected external provider account and credential;
- `PlatformCloudProvider`: future only and not required for V1.

The control-plane pricing below is therefore not a product-generation price.

---

## 2. Component-to-product mapping

| Control-plane component | Initial provider product | Region / placement | Initial capacity and operating rule |
|---|---|---|---|
| App Node | DigitalOcean Basic / Shared CPU Droplet | SGP1 VPC | 4 vCPU / 8 GiB RAM / 160 GiB bundled disk; `SIZE_M_MARGINAL`; FastAPI, E5 query embedding, retrieval, context, citation, frontend/nginx, Redis, Cloudflare connector, small control-plane services. No sustained indexing by default. |
| Worker Node | DigitalOcean Basic / Shared CPU Droplet | SGP1 VPC | 4 vCPU / 8 GiB RAM / 160 GiB bundled disk; one indexing worker initially; processing and general workers only under the P2B.1 concurrency rule. |
| Canonical database | DigitalOcean Managed PostgreSQL, Standard Edition / Basic shared CPU | SGP1 VPC/private hostname | 1 vCPU / 2 GiB RAM; smallest provider-accepted storage allocation for this class. |
| Canonical objects | DigitalOcean Spaces, Standard | SGP1 bucket | Private S3-compatible bucket, isolated per environment. |
| Redis | Existing Redis container with persistent data path on App Node | App Node private network | RQ queues/results, rate limits, leases; no managed Redis purchase in V1. |
| Public ingress | Cloudflare DNS + Tunnel + same-origin nginx route | Cloudflare edge to App Node | Keep the existing working ingress pattern; no public application ports required. |

DigitalOcean's current published Basic 4 vCPU / 8 GiB Droplet plan includes 160 GiB SSD, exceeding the topology's preferred 40 GiB app disk. Basic is shared CPU; the P2A benchmark does not claim equivalence to this cloud CPU. The upgrade path is Basic 4 vCPU / 8 GiB to CPU-Optimized 4 vCPU / 8 GiB only after cloud measurements justify it.

The worker maps the vendor-neutral 4 vCPU / 6 GiB target to the closest practical plan above it. CPU is expected to constrain indexing before RAM. Do not preemptively upgrade or run unrestricted indexing concurrency.

---

## 3. Network and runtime mapping

```text
PUBLIC
Browser -> Cloudflare DNS / TLS / Tunnel -> same-origin nginx on App Node

PRIVATE SGP1 VPC
App Node <--> Managed PostgreSQL private hostname + TLS
App Node <--> App Node Redis private endpoint
App Node <--> Spaces SGP1 endpoint through VPC-local DNS resolver
Worker Node <--> Managed PostgreSQL private hostname + TLS
Worker Node <--> App Node Redis private endpoint
Worker Node <--> Spaces SGP1 endpoint through VPC-local DNS resolver
```

Create one production SGP1 VPC in the later provisioning phase. App Node, Worker Node, and Managed PostgreSQL must use private addresses/private connection where supported. PostgreSQL must not require public database access.

For Spaces, each Droplet must use DigitalOcean's VPC-local DNS resolver. This preserves DigitalOcean's documented private internal route to Spaces rather than resolving the public endpoint. The application still uses the normal S3 endpoint hostname (for example, `sgp1.digitaloceanspaces.com`); the resolver determines the private route. Provisioning must verify resolver configuration from both nodes.

Redis is colocated but must be reachable from the Worker Node through a private App Node DNS name or private IP, not the Compose-only hostname `redis`. Configure `REDIS_URL` with that private endpoint; expose Redis only on the private interface/firewall scope required by App and Worker. This satisfies the cloud-control-plane preflight rule while preserving the selected colocated-Redis design.

---

## 4. Managed PostgreSQL requirements

DigitalOcean Managed PostgreSQL Standard Edition is selected at 1 vCPU / 2 GiB because the measured corpus is only 44 documents, 613 chunks/vector rows, and about 16 MiB database size. Do not provision the P2B.1 preferred 2 vCPU / 4 GiB class initially.

Required migration acceptance checks, before any canonical migration:

1. obtain private hostname and TLS connection details in the SGP1 VPC;
2. execute `CREATE EXTENSION vector` with the deployment database role;
3. confirm `vector(768)` columns and cosine operator usage;
4. create/inspect the required HNSW `vector_cosine_ops` index;
5. confirm PostgreSQL full-text `tsvector`, GIN, `to_tsvector('simple', ...)`, and `ts_rank_cd` behavior;
6. record the provider's actual PostgreSQL and pgvector extension versions;
7. validate backup/PITR and the repository's paired PostgreSQL/object recovery procedure.

The repository currently uses 768-dimensional vectors, pgvector HNSW with `vector_cosine_ops`, and GIN over `lexical_tsv`. DigitalOcean documents `vector`, HNSW/IVFFlat, and PostgreSQL hybrid full-text/vector search support; it does not remove the need to run these acceptance checks against the provisioned version. No vectorscale or alternative index type is selected.

The managed database's automatic backups/PITR are useful platform features but do not replace the repository's paired database/object export, reconciliation, and restore contract. App/Worker Droplet backups are operational convenience, not canonical database backups.

---

## 5. Spaces mapping

DigitalOcean Spaces Standard in SGP1 is the V1 canonical object store. It supplies the S3-compatible endpoint, private access keys, TLS, lifecycle support, and same-provider operational simplicity required by the topology.

Existing configuration maps without a storage-layer rewrite:

| Runtime setting | DigitalOcean Spaces value at provisioning |
|---|---|
| `MINIO_ENDPOINT` | SGP1 endpoint hostname, e.g. `sgp1.digitaloceanspaces.com` |
| `MINIO_BUCKET` | Separate private bucket name per environment |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Limited, per-environment Spaces access key pair |
| `MINIO_SECURE` | `true` |
| Region | Inferred from the endpoint; current client has no separate region setting |

The existing MinIO Python client uses endpoint, credentials, secure transport, and standard object methods only; Spaces' S3-compatible API supports the needed bucket/object operations. Preserve object names and semantics, including `document_id/original.pdf`; the internal `minio://` storage URI convention is not a provider API dependency.

Cloudflare R2 remains a future S3-compatible portability alternative, but is not the V1 canonical object store.

---

## 6. Cloudflare and staging rule

Cloudflare remains external DNS/TLS/ingress. The initial cloud ingress uses a Cloudflare Tunnel and same-origin nginx routing because this is the proven current path and removes the need to publish application ports on the Droplet. Direct Cloudflare proxying to a public Droplet origin is deferred.

Provision staging first at `staging.zkd.id.vn`, using a separate tunnel/hostname and fully separate cloud state. Never add a cloud connector as a second origin for `rag.zkd.id.vn` while the PC-backed and cloud stacks contain divergent canonical state.

The later sequence is:

```text
cloud staging -> migration validation -> data-migration rehearsal
-> production cutover -> post-cutover validation
```

No staging resource, tunnel, hostname, DNS record, or cutover is created here.

---

## 7. Configuration and secret inventory

No real values are created or committed. Runtime secrets/configuration required for this map include:

| Area | Required setting/value class |
|---|---|
| Database | `DATABASE_URL` using Managed PostgreSQL private hostname, database user/password, port, and TLS parameters |
| Redis | `REDIS_URL` using the App Node private DNS/IP and selected Redis port/database |
| Spaces | `MINIO_ENDPOINT`, `MINIO_BUCKET`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE=true` |
| Ingress | `CLOUDFLARE_TUNNEL_TOKEN`, `CLOUDFLARE_PUBLIC_ORIGIN` |
| Browser security | `AUTH_COOKIE_SECURE=true`, `AUTH_TRUSTED_ORIGINS`, `SECURITY_HSTS_ENABLED=true`, `TRUSTED_PROXY_CIDRS` |
| Release/recovery | `DEPLOYMENT_PROFILE=cloud_control_plane`, `RELEASE_ID`, encrypted/separate-failure-domain backup settings, absolute recovery-control and backup paths |
| E5 | `EMBEDDING_DEVICE=cpu`, persistent validated `EMBEDDING_MODEL_CACHE_DIR` |
| Existing generation runtime | current `GENERATION_*` / `OLLAMA_BASE_URL` values remain separately owned runtime configuration; this map supplies no platform-funded inference endpoint or cost |

The cloud-control-plane profile already rejects Docker-local database, Redis, and object endpoints; requires object-storage TLS; and validates persistent E5 artifacts. Its current external-generation-endpoint check is an existing Block 6 runtime integration dependency, not a DigitalOcean or platform-funded-LLM selection made by this document.

---

## 8. Price snapshot

**`PRICE_SNAPSHOT_2026_09_01`** — list-price planning assumptions only. They are not contractual prices, estimates of tax, currency conversions, or promotional-credit claims.

| Component | Assumption | Monthly USD |
|---|---|---:|
| App Node | DigitalOcean Basic 4 vCPU / 8 GiB | 48.00 |
| Worker Node | DigitalOcean Basic 4 vCPU / 8 GiB | 48.00 |
| Managed PostgreSQL | Basic 1 vCPU / 2 GiB, smallest currently practical provider storage | approximately 30.45 |
| Spaces Standard | Base subscription | 5.00 |
| Redis | Colocated App Node container | 0 incremental infrastructure purchase |
| Generation | Excluded | — |

Indicative selected control-plane base: approximately **USD 131.45/month** before taxes, transfer overages, storage overages, backup products, monitoring, support, optional IP/NAT/network products, or other provider charges. This is not an approved spend or provisioning instruction.

---

## 9. Alternatives and remaining uncertainties

**Runner-up: Vultr Singapore.** It remains viable because official documentation supports managed PostgreSQL `vector`/HNSW and VPC-attached database provisioning. It is not selected; no multi-cloud architecture is created.

AWS/hyperscaler migration and Cloudflare R2 remain possible through the current database URL, S3-compatible storage, Redis URL, artifact-cache, and ingress boundaries.

Provider-specific items deferred to the provisioning/migration phase:

- exact SGP1 availability, selected Droplet CPU generation, and actual cloud benchmark results;
- exact Managed PostgreSQL storage minimum, engine/extension version, private hostname, TLS mode, connection limit, PITR/backup terms, and recovery exercise;
- Spaces bucket/access-key creation, private resolver verification, lifecycle/durability/egress terms, and separate staging bucket;
- VPC CIDR, firewall rules, private DNS names, Redis private bind/port, and tunnel identity;
- secret injection mechanism, monitoring/logging, backup destination, and staging/prod environment creation;
- data migration rehearsal and production cutover;
- every LLM/GPU/provider-credential/billing decision.

### External validation sources

- [DigitalOcean Droplet pricing](https://www.digitalocean.com/pricing/droplets) — 4 vCPU / 8 GiB Basic plan and CPU-Optimized upgrade mapping.
- [DigitalOcean Managed Databases pricing](https://www.digitalocean.com/pricing/managed-databases) — 1 vCPU / 2 GiB PostgreSQL price snapshot and storage range.
- [DigitalOcean Managed PostgreSQL vector search](https://docs.digitalocean.com/products/vector-databases/postgresql/) — `vector`, HNSW, GIN/full-text hybrid support.
- [DigitalOcean PostgreSQL connection documentation](https://docs.digitalocean.com/products/databases/postgresql/how-to/connect/) — VPC private hostname and TLS.
- [DigitalOcean Spaces pricing](https://docs.digitalocean.com/products/spaces/details/pricing/) and [S3 compatibility](https://docs.digitalocean.com/products/spaces/reference/s3-compatibility/) — private VPC-local DNS route and S3-compatible API.
- [Vultr pgvector documentation](https://docs.vultr.com/ai-powered-search-with-pgvector-and-vultr-managed-database-for-postgresql) — runner-up viability.

---

## 10. Freeze statement

This document freezes the V1 provider mapping: DigitalOcean in SGP1 for control-plane compute, managed PostgreSQL, and Spaces; colocated persistent Redis; and Cloudflare ingress. It does not amend the Hybrid Runtime Contract, vendor-neutral topology, Blocks 1–6, generation funding, or application behavior.

```text
CLOUD_PROVIDER_SELECTION_V1
STATUS: FROZEN V1 PROVIDER MAP
```
