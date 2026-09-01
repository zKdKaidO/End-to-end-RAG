# STAGING_PROVISIONING_RUNBOOK_V1

**Status:** Preparation only — no resource creation is authorized by this document.
**Provider:** DigitalOcean / SGP1
**Staging hostname:** `staging.zkd.id.vn`
**Production protection:** `rag.zkd.id.vn` and its existing PC tunnel remain untouched.

## 1. Scope and guardrails

This runbook prepares an isolated cloud staging control plane. It does not authorize `terraform apply`, DigitalOcean API mutations, Cloudflare changes, canonical-data migration, production cutover, GPU/Qwen/Ollama cloud deployment, centralized LLM spend, or any provider billing action.

Before P2B.3B, a human must review the Terraform plan and explicitly approve creation of the billable staging resource set. Never use `docker compose down -v` against development or production. A future `terraform destroy` must use only the staging state and separately approved scope.

## 2. Resource inventory and deterministic names

| Resource | Name / class | Boundary |
|---|---|---|
| VPC | `zkd-rag-staging-vpc`, SGP1 | staging only |
| App Droplet | `zkd-rag-staging-app`, Basic 4 vCPU / 8 GiB, Ubuntu `ubuntu-24-04-x64` | staging only |
| Worker Droplet | `zkd-rag-staging-worker`, Basic 4 vCPU / 8 GiB, Ubuntu `ubuntu-24-04-x64` | staging only |
| Managed PostgreSQL | `zkd-rag-staging-db`, Standard Basic 1 vCPU / 2 GiB | private VPC staging database |
| Spaces | `zkd-rag-staging-<unique-suffix>` | private SGP1 staging bucket |
| Redis | Docker container on App Node, durable host path | private operational state |
| Cloudflare Tunnel | new staging-only tunnel | never production tunnel |
| DNS | `staging.zkd.id.vn` -> staging tunnel only | never production hostname |

Names must contain no credential or user-identifying value. The Spaces suffix must be globally unique and lowercase.

## 3. Network, firewall, and host bootstrap

Create one SGP1 VPC later. App, Worker, and Managed PostgreSQL use private connectivity. PostgreSQL must use its private hostname with TLS; do not open public database access.

The Terraform firewall declaration allows optional SSH only from the operator-provided administrative CIDR, exposes no broad HTTP/HTTPS application port, and permits Redis TCP/6379 only from the Worker tag. Redis is bound to the App Node VPC IPv4, protected by the VPC/firewall, and must use a strong password. Worker has no public application ingress.

Host bootstrap later installs Docker Engine and the Docker Compose plugin, creates durable `/opt/zkd-rag/staging/*` paths with restrictive permissions, installs no application dependency on the host, and places all application work in containers. Apply normal OS patching and non-password SSH hardening under the operator's host policy.

## 4. Terraform workflow

IaC is at `deployment/terraform/staging/`. It describes DigitalOcean infrastructure only; Cloudflare is intentionally human/manual in this phase.

```text
export DIGITALOCEAN_TOKEN=...                         # never persist in shell history or Git
cp terraform.tfvars.example terraform.tfvars          # untracked, placeholders replaced after review
terraform init -backend=false
terraform fmt -check
terraform validate
terraform plan -out=tfplan
```

Inspect the plan for only the seven intended Terraform-managed staging objects: VPC, two Droplets, Managed PostgreSQL, private Spaces bucket, and two Droplet firewalls. Redis and Cloudflare are separate later operational steps. Human approval is required before any later `terraform apply`. Do not create/import an SSH private key; pass only an existing DigitalOcean public-key ID/fingerprint.

## 5. App/Worker deployment roles

Use `deployment/docker-compose.cloud-control-plane.yml` plus `deployment/docker-compose.cloud-control-plane.staging.yml`.

| Node | Compose role | Services |
|---|---|---|
| App Node | `--profile app` | API, frontend/nginx, Redis, Cloudflare staging connector |
| Worker Node | `--profile worker` | general worker, processing worker, indexing worker |
| App Node maintenance only | `--profile operations` | `db-migrate`, `deployment-tool` |

The cloud Compose contains no local PostgreSQL, MinIO, or Ollama/Qwen. PostgreSQL and Spaces stay external. API/indexing mount the prevalidated E5 cache read-only. Run database migration only from the App Node after database acceptance succeeds. Run one indexing worker initially.

On each host, point Compose interpolation and service `env_file` at the protected staging runtime file. On the App Node also point the connector only at the protected staging tunnel-token file:

```text
export CLOUD_CONTROL_PLANE_ENV_FILE=/opt/zkd-rag/staging/.env.staging
export CLOUDFLARE_TUNNEL_ENV_FILE=/opt/zkd-rag/staging/.env.cloudflare.staging
docker compose --env-file "$CLOUD_CONTROL_PLANE_ENV_FILE" \
  -f deployment/docker-compose.cloud-control-plane.yml \
  -f deployment/docker-compose.cloud-control-plane.staging.yml --profile app up -d
```

On the Worker Node, set only `CLOUD_CONTROL_PLANE_ENV_FILE` and start `--profile worker`. Use `--profile operations` only on the App Node for the explicitly invoked migration/operations command. These commands are for the later approved provisioning phase, not an instruction to start staging now.

## 6. Environment and secret inventory

Copy `.env.staging.example` and `.env.cloudflare.staging.example` to untracked protected staging-host files. Required human-supplied values are:

| Secret/config class | Required value |
|---|---|
| DigitalOcean provisioning | `DIGITALOCEAN_TOKEN`; existing SSH public-key ID/fingerprint |
| Managed PostgreSQL | private hostname, port, database/user/password, TLS parameters |
| Redis | strong `REDIS_PASSWORD`, App VPC bind address/private DNS, matching URL-encoded `REDIS_URL` |
| Spaces | SGP1 endpoint, staging bucket, limited access key/secret, TLS enabled |
| Cloudflare staging | new staging-only `TUNNEL_TOKEN`; never the production token |
| Application security | staging trusted origin, trusted proxy CIDRs, release ID/commit identity |
| Recovery/export | encrypted separate-failure-domain backup destination and control-path configuration |
| E5 | prepopulated canonical cache path |
| Existing generation runtime | separately owned external endpoint configuration; no platform-funded endpoint is created here |

## 7. PostgreSQL acceptance before data migration

Do not trust provider marketing alone. From the App Node, then Worker Node where needed, use the private TLS database connection and run:

```text
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f deployment/terraform/staging/sql/postgresql_acceptance.sql
```

The script installs/checks `vector`, creates a temporary `vector(768)` table, creates HNSW `vector_cosine_ops` and GIN indexes, verifies PostgreSQL simple full-text behavior and cosine query execution, then rolls back the temporary objects. Record PostgreSQL and pgvector versions. Confirm private connectivity and TLS from both hosts before any canonical data migration.

## 8. Spaces acceptance before data migration

Use staging-only limited credentials and the configured SGP1 endpoint/TLS path. From each Droplet after VPC-local DNS verification:

1. PUT `acceptance/<random-id>.txt` into the staging bucket;
2. HEAD then GET it, comparing bytes;
3. DELETE that same staging-only key;
4. verify the endpoint resolved through the VPC-local DNS resolver/internal route;
5. record no production bucket/key was touched.

The application continues to use `MINIO_ENDPOINT`, `MINIO_BUCKET`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, and `MINIO_SECURE=true`; no storage code changes are allowed.

## 9. Redis staging contract

Redis uses append-only persistence at `REDIS_DATA_HOST_PATH`, `--requirepass`, and a host binding only to `REDIS_PRIVATE_BIND_ADDRESS`. The Worker uses the App Node private DNS/IP in `REDIS_URL`; it must not use Compose hostname `redis`, public IP, or Internet exposure. Redis is operational state for RQ, rate limits, and leases—not canonical document state and not harmless to lose.

## 10. E5 artifact bootstrap

The only canonical embedding model is `intfloat/multilingual-e5-base`. Before offline application startup, an explicit operator bootstrap must populate the host Hugging Face **hub** cache at `EMBEDDING_MODEL_CACHE_HOST_PATH`, directly containing:

```text
models--intfloat--multilingual-e5-base/
  refs/main
  snapshots/<revision>/config.json
  snapshots/<revision>/modules.json
  snapshots/<revision>/model.safetensors
  snapshots/<revision>/tokenizer_config.json
```

Bootstrap is a deliberate, logged one-time provisioning operation using the approved model source; do not permit app startup to download or substitute a model. Validate the exact layout with the existing `validate_canonical_e5_artifact` preflight before mounting it read-only to API/indexing containers. Do not commit model artifacts or reindex merely to populate a cache.

## 11. Cloudflare staging plan

After explicit later approval, a human creates a **new** Cloudflare Tunnel, stores its token only in the untracked `.env.cloudflare.staging` file, configures it to reach the App Node frontend, and creates `staging.zkd.id.vn` for that tunnel alone. Confirm same-origin `/api` routing.

Never use the production tunnel token, change `rag.zkd.id.vn`, or attach staging as a second connector/origin to production while canonical data differs.

## 12. Cost guard, rollback, and production protection

Current planning baseline: App USD 48/month, Worker USD 48/month, Managed PostgreSQL about USD 30.45/month, Spaces USD 5/month, Redis USD 0 incremental, generation excluded; approximately USD 131.45/month before taxes/variable services.

If later staging validation fails, stop the staging deployment and preserve diagnostics. Any cleanup must be scoped to the separate staging Terraform state and requires explicit human approval. It must never target local development, recovery, PC production, `rag.zkd.id.vn`, or canonical production data.

## 13. Later provisioning checklist

1. Confirm account/payment readiness and explicit approval of the billable resource set.
2. Create/import public SSH key and restrict the administrative CIDR.
3. Install Terraform, export `DIGITALOCEAN_TOKEN`, run `init`, `fmt`, `validate`, and inspect `plan`.
4. Obtain explicit approval before future `apply`.
5. Create only staging VPC/Droplets/database/Spaces/firewalls.
6. Retrieve private PostgreSQL/TLS details; create limited Spaces credentials; configure Redis private binding/password.
7. Bootstrap and validate E5 cache.
8. Create separate staging tunnel and `staging.zkd.id.vn`.
9. Run database and Spaces acceptance checks, then cloud-control-plane preflight/migration and staging smoke tests.
10. Do not perform data migration rehearsal, production cutover, or any production DNS/tunnel change in this phase.
