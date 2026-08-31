# Cloudflare Tunnel repository readiness

This document covers Phase 1A repository readiness. It does not create a
Cloudflare account resource or make the application publicly reachable.

## Public hostname

- Registered domain: `zkd.id.vn`
- Legal RAG application: `https://rag.zkd.id.vn`
- Cloudflare Published Application: `rag.zkd.id.vn` -> `http://frontend:80`

The root domain is reserved for a future homepage. Do not publish this Legal
RAG application at `zkd.id.vn`, `www.zkd.id.vn`, `api.zkd.id.vn`, or a direct
storage/database hostname.

## Architecture

The application remains entirely local:

```text
Internet
  -> Cloudflare edge
  -> Cloudflare Tunnel
  -> cloudflared
  -> frontend/nginx:80
       |-- React SPA
       `-- /api/* -> api:8000
                         -> PostgreSQL/pgvector, Redis/RQ, MinIO,
                            local embeddings, and Ollama/Qwen
```

Only `frontend:80` is an origin for the Tunnel. The override places
`cloudflared` and `frontend` on a dedicated `tunnel_ingress` network;
`cloudflared` is not attached to the API or private backend network. The API is
reachable from nginx through the existing `provider` network. PostgreSQL,
Redis, MinIO, Ollama, and workers are not Tunnel origins.

Cloudflare is ingress only. It is not the application runtime, database,
vector store, object store, queue, embedding provider, or generation provider.

## What Phase 1A provides

- A same-origin browser API gateway under `/api`.
- nginx proxy rules that preserve the existing backend paths.
- Explicit non-buffered proxying for both production SSE endpoints.
- An 11 MiB nginx request-body ceiling, allowing the backend's authoritative
  10 MiB PDF limit plus bounded multipart overhead.
- A separate `compose.cloudflare.yml` override with the official cloudflared
  image, a frontend health dependency, and `unless-stopped` restart behavior.
- A secret-free environment template and Git ignore protection.
- HTTPS-origin auth settings in the override without changing local Compose.

The base `docker-compose.yml` remains the normal local-development stack.

## Phase 1B operator setup

1. Wait until the `zkd.id.vn` DNS zone is **Active** in Cloudflare.
2. Create a remotely managed Cloudflare Tunnel and obtain its token.
3. Copy `.env.cloudflare.example` to the ignored `.env.cloudflare` file.
4. Set `CLOUDFLARE_TUNNEL_TOKEN` to the real token and
   `CLOUDFLARE_PUBLIC_ORIGIN` to the exact HTTPS origin, with no path or
   trailing slash: `https://rag.zkd.id.vn`.
5. Create the Cloudflare Published Application:

   ```text
   rag.zkd.id.vn -> http://frontend:80
   ```

   Do not point it at `localhost`, `host.docker.internal`, the API, or any
   private service.
6. Validate the Compose configuration from the repository root:

   ```sh
   docker compose \
     -f docker-compose.yml \
     -f compose.cloudflare.yml \
     --env-file .env.cloudflare \
     config --quiet
   ```

7. Start the stack from the repository root:

   ```sh
   docker compose \
     -f docker-compose.yml \
     -f compose.cloudflare.yml \
     --env-file .env.cloudflare \
     up -d
   ```

8. Verify that the Tunnel reports **Healthy** in Cloudflare.
9. Open `https://rag.zkd.id.vn`, then run the public end-to-end checklist
   below, including authenticated incremental SSE verification.
10. In Cloudflare Access, add defense-in-depth policies for `/debug*` and
   `/evaluation*`. Existing application authorization remains authoritative.

Cloudflare's current official setup, routing, and token guidance is available
at:

- <https://developers.cloudflare.com/tunnel/setup/>
- <https://developers.cloudflare.com/tunnel/routing/>
- <https://developers.cloudflare.com/tunnel/advanced/tunnel-tokens/>

Treat the Tunnel token as a secret. Do not place it in Compose YAML, images,
documentation, tests, shell history, or Git. Rotate it in Cloudflare if it is
ever exposed.

## Same-origin routing contract

The production frontend defaults to `/api`. nginx applies two deliberate path
rules:

| Browser request | FastAPI request |
| --- | --- |
| `/api/v1/auth/me` | `/api/v1/auth/me` |
| `/api/documents` | `/documents` |
| `/api/answer/stream` | `/answer/stream` |
| `/api/v1/chat/sessions/{id}/turns/stream` | same path |

This supports the backend's existing mix of `/api/v1/*` routes and root-level
routes without producing `/api/api/...`. The Vite development server applies
the same rewrite contract, so `npm run dev` remains usable at
`http://localhost:5173` when the API is available on port 8001.

The normal Docker frontend remains available locally at
`http://localhost:5173`; its `/api` requests are served by nginx. Explicitly
setting `VITE_API_BASE_URL` to an absolute API URL remains available for a
special local build, but is not the production default.

## Streaming

nginx handles these endpoints specially:

- `/api/answer/stream`
- `/api/v1/chat/sessions/{id}/turns/stream`

They use HTTP/1.1, clear the hop-by-hop `Connection` header, disable response
buffering and proxy caching, and allow a five-minute upstream read interval.
The browser therefore receives the backend's `start`, incremental `delta`, and
terminal SSE events without nginx waiting for the whole response. Ordinary API
responses retain normal proxy buffering.

During Phase 1B, open browser developer tools, submit a real Ask request, and
confirm multiple `delta` events/text updates arrive before the terminal event.
Also verify that Stop generation cancels the active stream. A final HTTP 200
alone is not sufficient evidence of incremental streaming.

## PDF uploads

PDF uploads follow the unchanged path:

```text
browser -> /api/documents -> frontend/nginx -> /documents -> FastAPI -> MinIO
```

nginx accepts up to 11 MiB at the gateway. FastAPI retains the authoritative
10 MiB PDF file limit and all existing validation, processing, storage, and
lifecycle behavior. Cloudflare plan/request limits must also be checked by the
operator; Phase 1A does not attempt to bypass them.

## Auth, cookies, and CORS

The public application is one HTTPS origin. Browser API requests therefore use
same-origin credentials rather than permissive cross-origin CORS. The override
sets secure cookies, the exact trusted public origin, and HSTS for API
responses. It does not add wildcard CORS, weaken CSRF/origin checks, disable
TLS verification, or introduce Cloudflare-specific backend authentication.

The base local stack is unchanged and continues using its local HTTP cookie and
origin settings when the Cloudflare override is absent.

## Published host ports

All current host mappings bind only to `127.0.0.1`; none should be exposed on a
public interface:

| Host mapping | Classification |
| --- | --- |
| `127.0.0.1:5173 -> frontend:80` | Local development only |
| `127.0.0.1:8001 -> api:8000` | Local development/diagnostics only; never a public API |
| `127.0.0.1:5432 -> postgres:5432` | Local development only; PostgreSQL must not be public |
| `127.0.0.1:6379 -> redis:6379` | Local development only; Redis must not be public |
| `127.0.0.1:9000 -> minio:9000` | Local development only; MinIO API must not be public |
| `127.0.0.1:9001 -> minio:9001` | Local development only; MinIO console must not be public |

The Tunnel uses Docker networking and needs no inbound host port. Host firewall
and router rules must not publish the loopback development ports.

## Phase 1B public end-to-end gate

Public deployment is not a PASS until a human verifies every item:

- [ ] HTTPS product loads
- [ ] Login works
- [ ] `/ask` works
- [ ] `/documents` works
- [ ] Direct `/ask` refresh works
- [ ] Direct `/documents` refresh works
- [ ] Chat visibly streams incrementally
- [ ] Stop generation works
- [ ] Chat history works
- [ ] Citations/evidence work
- [ ] Multi-document scope works
- [ ] PDF upload works
- [ ] Processing lifecycle works
- [ ] Indexing works
- [ ] Retry indexing works
- [ ] Document delete works
- [ ] Manual refresh works
- [ ] Internal/admin routes receive additional Cloudflare Access protection
- [ ] API is not separately exposed publicly
- [ ] PostgreSQL is not public
- [ ] Redis is not public
- [ ] MinIO is not public
- [ ] Ollama is not public
- [ ] Tunnel container restart recovers
- [ ] PC reboot recovery is understood/tested

**PC DOWN = APPLICATION ORIGIN DOWN.** This is expected in Phase 1. Cloudflare
Tunnel does not provide origin high availability.

## Deferred by design

Phase 1A does not implement compute/GPU failover, database or vector
replication, cloud backup, R2, D1, Vectorize, Workers AI, AI Gateway,
Cloudflare Queues, Workflows, Containers, a Workers fallback, a serverless
backend, cloud processing, cloud embedding/generation, or Deployment Profile
Block 7. These require separately reviewed future phases.
