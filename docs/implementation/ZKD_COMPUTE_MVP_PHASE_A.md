# ZKD Compute MVP — Phase A

**Status:** Implemented skeleton; browser acceptance remains an external gate.
**Scope:** P2C.4A only — loopback control runtime and synthetic transport proof.

## Scope and non-interference

`app/local_compute/` is a self-contained control-service foundation. It is not
registered in `app/main.py`, does not alter Blocks 1–6, and performs no document
acceptance, PDF parsing, E5 loading, indexing, retrieval, context construction,
generation, cloud request, or model download. The public frontend is untouched.

The isolated synthetic transport probe is described in
`evaluation/local_compute_transport/README.md` and tested in
`tests/unit/local_compute/test_runtime.py`.

## Transport implementation and evidence

The listener binds only to literal `127.0.0.1`, using port `0` so the OS chooses
an ephemeral port. Each `LocalComputeRuntime` has a fresh opaque endpoint
generation. `LoopbackControlServer` owns listener startup/shutdown and does not
bind a hostname, LAN address, IPv6 address, or public interface.

The test starts a real loopback HTTP listener and transfers only a synthetic
binary body directly to `/v1/probe/binary`. It verifies an exact allowed origin,
an OPTIONS preflight with `Access-Control-Allow-Private-Network: true`, MAC
authentication after CORS admission, and foreign-origin denial. No wildcard
CORS or arbitrary origin reflection is present. A failing or absent browser
automation surface does not convert these HTTP tests into browser evidence.

## Origin policy

Production allowlist: `https://rag.zkd.id.vn`.

Development origins are accepted only when `development_mode=True` and supplied
in the explicit `development_origins` tuple. Production configuration rejects
development origins. Responses to rejected origins contain a typed error and no
runtime/device metadata. Preflight permits fixed methods and headers only.

## Session/authentication foundation

`LocalSessionManager` creates random, memory-only sessions after grant
verification. Production uses `UnavailableGrantVerifier` and fails closed with
`NOT_PAIRED` until a real cloud pairing verifier exists. The only development
grant verifier is available behind explicit development mode and exists solely
for isolated tests.

Sensitive routes require the P2C.3-shaped headers:

```text
X-ZKD-Local-Session
X-ZKD-Timestamp
X-ZKD-Nonce
X-ZKD-MAC = HMAC(session_key, method | path | timestamp | nonce | SHA256(body))
X-ZKD-Protocol-Version
```

The runtime rejects missing authentication, expired sessions/timestamps, MAC or
body-hash mismatch, nonce replay, origin mismatch, and incompatible protocol.
It never uses the platform cookie as local authorization and does not persist a
browser bearer secret.

## Runtime contract

`protocol_version` is `zkd-compute-v1`; `runtime_version` is `0.1.0`.
Runtime states supported by the skeleton are `OFFLINE`, `CONNECTING`,
`AUTHENTICATING`, `READY`, `BUSY`, `DEGRADED`, `UNAVAILABLE`, `REVOKED`, and
`UPDATE_REQUIRED`. Startup creates the data root, initializes the catalog, and
becomes `READY` only for the control service. Shutdown marks it `OFFLINE` and
releases the listener.

Capabilities are honestly reported as `NOT_READY` for `pdf_processing`,
`chunking`, `embedding`, `indexing`, `retrieval`, and `generation`; no
capability is faked.

## Data root, catalog, jobs, and manifest boundary

The default Windows root resolves from `%LOCALAPPDATA%` without a username to
`%LOCALAPPDATA%\\ZKD\\Compute`. Tests pass a temporary root. Phase A creates only
`state/`, `logs/`, and `tmp/` — never a document, artifact, model, or fake PDF.

`state/catalog.sqlite3` has explicit schema version `1`, `runtime_metadata`,
and a minimal durable `local_jobs` table. `LocalJobStore` records only a
non-executing skeleton lifecycle foundation. There is no Redis/RQ dependency.
`ManifestSyncClient` is an intentionally unavailable interface in Phase A:
later it must be an outbound metadata-only boundary and may never upload
document/RAG content.

## Logging, errors, and limits

The runtime emits privacy-safe JSONL audit events under `logs/runtime.jsonl` for
request ID, operation, duration, and status only. It never logs session keys,
grants, MACs, headers, request bodies, local paths, or future document content.
API responses are typed, content-free errors: `NOT_PAIRED`, `SESSION_EXPIRED`,
`ORIGIN_NOT_ALLOWED`, `AUTH_REQUIRED`, `AUTH_INVALID`, `REPLAY_DETECTED`,
`UPDATE_REQUIRED`, `CAPABILITY_UNAVAILABLE`, `INVALID_REQUEST`,
`PAYLOAD_TOO_LARGE`, and `INTERNAL_COMPUTE_ERROR`. No Python traceback, grant,
session key, MAC, body, or local path is returned. The request-size, session,
nonce, and skeleton-concurrency limits are centralized in
`LocalComputeSettings`.

## Validation

Run from the API container:

```text
python -m pytest tests/unit/local_compute -v
```

The Phase-A test set covers loopback-only configuration, temporary data roots,
production fail-closed grants, exact origin/PNA preflight, no wildcard CORS,
foreign-origin denial, authenticated runtime/capabilities, missing/invalid/replay
and body-hash authentication failures, protocol mismatch, direct synthetic
binary transfer, request-size rejection, an OS-assigned endpoint, and SQLite
job persistence across restart.

## Known limitations and next phase

No Chrome/Edge automation was executable through the available browser-control
runtime on this host, so this is **not** a browser acceptance pass. Chrome and
Edge must execute the same synthetic test from an HTTPS product-equivalent
origin before desktop release, without security flags.

The exact next implementation scope is **P2C.4B LOCAL DOCUMENT ACCEPTANCE +
PREPARATION FOUNDATION**: implement local `DocumentStore` admission and managed
source copying behind the protocol, without changing the frozen production
pipeline.
