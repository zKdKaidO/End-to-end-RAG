# Cloud control-plane endpoint inventory

This inventory is based on the frontend API client, browser Compute platform
client, local Compute production launcher, and local Compute control channel.

## Retained in the Worker

| Consumer | Route | Reason |
| --- | --- | --- |
| browser | `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me` | minimal same-origin account/session boundary |
| browser | `POST /api/v1/compute/pairing-challenges` | browser starts a short-lived pairing flow |
| browser | `POST /api/v1/compute/pairing-challenges/:id/confirm` | owner confirms physical/local device pairing |
| browser | `GET /api/v1/compute/devices` | device discovery and ready/offline status |
| browser | `POST /api/v1/compute/devices/:id/revoke` | credential-epoch revocation |
| browser | `POST /api/v1/compute/devices/:id/local-session-grants` | origin-, nonce-, device-, epoch-, generation-bound local grant |
| browser | `GET /api/v1/compute/local-manifests` | metadata-only document discovery/queryability |
| local Compute | `POST /api/v1/compute/control/pairing-challenges/:id/complete` | signed proof of device public-key possession |
| local Compute | `POST /api/v1/compute/control/presence` | signed low-frequency HTTP presence heartbeat |
| local Compute | `POST /api/v1/compute/control/manifests` | signed metadata-only manifest publication |
| health check | `GET /health` | Worker liveness only |

The device channel is outbound HTTPS polling/heartbeat, not a WebSocket. No
Durable Object is needed.

## Local-only: never port

The browser calls the installed `127.0.0.1` Compute endpoint after obtaining a
grant. Its document upload/preparation/indexing, SQLite retrieval, E5,
context, citation, local/provider generation, history and endpoint-generation
checks remain local. `zkd://start` remains a browser-to-installed-app action.

## Legacy/Docker-specific: not ported

The former FastAPI/PostgreSQL/Redis/MinIO surface for `/documents`, chunks,
retrieval/answer generation, chat history, evaluation, debug, worker jobs,
object reconciliation, and the legacy `/ready` dependency probe is not a
Cloudflare control-plane API. It belongs to the retained development stack,
not production.

## Storage mapping

| Legacy component | Previous responsibility | Production Cloudflare disposition |
| --- | --- | --- |
| PostgreSQL + pgvector | auth, control metadata, documents/chunks/vectors/history | D1 keeps only auth/control metadata; document/RAG state is local SQLite |
| Redis/RQ | cloud pipeline/background jobs | removed; document work is local synchronous/on-device work |
| MinIO | server-side source objects | removed; canonical document bytes stay in local Compute storage |
| cloudflared tunnel | exposed developer-PC frontend/API | removed after successful Worker custom-domain cutover |
