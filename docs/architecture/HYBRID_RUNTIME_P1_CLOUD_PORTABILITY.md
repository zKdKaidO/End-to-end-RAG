# Hybrid Runtime Migration — P1 Cloud Portability Boundary

## Scope

P1 establishes deployment topology configuration for the same Legal RAG
application source. It does not provision cloud infrastructure, migrate
canonical data, alter Blocks 1–6, provide cloud generation, or make the
product always-online. Those are later Hybrid Runtime Contract phases.

The frozen [Hybrid Runtime Contract V1](HYBRID_RUNTIME_CONTRACT_V1.md) remains
the governing architecture document.

## Deployment profiles

`DEPLOYMENT_PROFILE` is a topology selector only. It does not select chunking,
embeddings, retrieval, RRF, context construction, citation behavior, or any
other RAG semantic.

| Profile | Intended topology | Endpoint policy |
| --- | --- | --- |
| `local_dev` | Developer Docker Compose with source bind mounts | Docker-local service names are allowed. |
| `pc_tunnel` | Current PC-hosted runtime reached through Cloudflare Tunnel | Local runtime services are allowed; HTTPS origin, secure cookie, HSTS, trusted proxy settings are required. |
| `self_hosted` | Existing all-in-one immutable-image deployment stack | Local Docker dependencies plus production recovery/model checks are required. |
| `cloud_control_plane` | Future always-online application containers connected to externally provisioned services | PostgreSQL, Redis, object storage, and generation endpoint must not use local/Docker-only hosts. |

The former `development` and `production` values remain accepted aliases for
`local_dev` and `self_hosted`; this preserves existing deployment behavior.

## Portable application topology

`deployment/docker-compose.cloud-control-plane.yml` is application-only:

```text
frontend -> nginx same-origin /api -> api -> external PostgreSQL + pgvector
                                  -> external Redis/RQ
                                  -> external S3-compatible object storage
                                  -> provisioned read-only E5 cache
workers  -> the same external PostgreSQL, Redis/RQ, object storage, E5 cache
```

It publishes no PostgreSQL, Redis, MinIO, or FastAPI ports and has no source
bind mount into `/app`. An outer platform ingress attaches to `frontend`; the
current Cloudflare-on-PC route remains Cloudflare -> cloudflared -> frontend ->
nginx -> `/api` -> FastAPI.

Copy `.env.cloud-control-plane.example` to an untracked runtime environment
file and inject secrets through the process/container environment. The tracked
template contains placeholders only. P1 chooses no cloud vendor and does not
start this topology.

## Service boundaries retained

- Database and Redis already use externally supplied URLs; P1 does not alter
  migrations, PostgreSQL 15/pgvector behavior, queues, retries, or schema.
- The existing MinIO client remains the one S3-compatible storage boundary.
  Its endpoint, credentials, bucket, and TLS mode are configuration values;
  the existing `minio://` logical object identifier is deliberately unchanged.
- The frozen `intfloat/multilingual-e5-base` artifact remains CPU-configured,
  offline, 768-dimensional, normalized, and prefix-compatible. Its cache path
  is now explicit (`EMBEDDING_MODEL_CACHE_DIR`). Its value is the Hugging Face
  hub cache directory that directly contains the canonical `models--…` entry;
  the portable Compose mounts that directory read-only. A missing or incomplete
  cache fails model initialization and readiness before a model lookup; P1 never downloads
  an alternate model or reindexes.
- `OLLAMA_BASE_URL` remains a runtime setting. `cloud_control_plane` validates
  that it is externally addressed, but readiness intentionally does not demand
  Qwen availability until the P4 generation-provider phase.
- Recovery control and backup directories remain operational artifacts rather
  than canonical data. They are configurable, require durable absolute paths
  in the cloud-control-plane profile, and are mounted explicitly by Compose.

## Profile-aware preflight

The cloud-control-plane preflight rejects Docker-only/local database, Redis,
object-store, or generation endpoints; requires TLS object storage, secure
public-origin controls, durable recovery paths, and a provisioned E5 cache.
It does not connect to a cloud vendor during configuration validation. Local
development retains Docker hostnames and relaxed local recovery defaults.

## What P1 does not do

P1 does not migrate PostgreSQL or objects, create databases or queues, select
a provider, run cloud generation, register devices, add transport, or change
the existing PC deployment. It is a portability boundary for P2/P3, not an
always-online release.
