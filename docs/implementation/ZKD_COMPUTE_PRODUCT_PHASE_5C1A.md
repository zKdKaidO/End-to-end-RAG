# ZKD Compute Product Phase 5C1A — Browser Compute Integration Foundation

## Scope

This phase adds no product UI and changes nothing under `frontend/`. It provides a
test-only browser-compatible signing reference, deterministic vectors, an isolated
browser-like harness, and the contract needed for the later human-owned client.
Browser-to-platform traffic remains account/discovery/grant metadata only. Browser
to `127.0.0.1` carries local document, retrieval, and generation operations.

## Platform browser API audit

| Purpose | Authenticated platform route | Current response / important fields |
| --- | --- | --- |
| Device discovery | `GET /api/v1/compute/devices` | `devices[]`: ID, state, protocol/runtime versions, endpoint generation/port, capabilities |
| Local metadata read model | `GET /api/v1/compute/local-manifests` | device/document IDs, preparation/index/local availability, artifact compatibility, queryable and generation flags |
| Local-session grant | `POST /api/v1/compute/devices/{device_id}/local-session-grants` | body currently requires `browser_nonce`; trusted `Origin`; response includes one-time signed `local_access_grant`, expiry, device ID, endpoint generation |
| Local bootstrap | `POST http://127.0.0.1:{port}/v1/sessions` | signed grant plus browser nonce; returns memory-only session ID/key, expiry, operations, protocol and endpoint generation |

The platform request must use the current product `Origin` (`https://rag.zkd.id.vn`).
The current grant route issues the frozen operation set `documents`, `jobs`,
`retrieval`, `answer`; it does not presently accept an operation-subset field. The
future product should treat Documents as needing `documents`/`jobs` and Ask as
needing `retrieval`/`answer`, but must not pretend it can narrow the present grant
without a separately approved platform-contract amendment.

## Device selection and loopback derivation

Select a device only when it is owned by the current user and its discovery record
has all of: `READY` state, protocol `zkd-compute-v1`, non-empty runtime version,
non-empty endpoint generation, port in `1..65535`, and required capability of
`READY` or `ADMITTED`. Manifest existence alone is insufficient.

The only permitted local base URL is exactly:

```text
http://127.0.0.1:<endpoint_port>
```

Never derive a LAN, hostname, Tailscale, or public endpoint. A changed device ID or
endpoint generation discards the entire in-memory local session immediately.

## Browser nonce, grant, and session

Generate a fresh, high-entropy browser nonce with Web Crypto-compatible randomness
for each bootstrap attempt. Send it both in the platform grant request body and as
`X-ZKD-Browser-Nonce` to local bootstrap. On successful bootstrap discard the grant;
it is short-lived and one-time.

Keep this state in process memory only:

```text
deviceId, endpointGeneration, baseUrl, sessionId, sessionSecret,
expiresAt, allowedOperations, protocolVersion
```

Do not place the session secret in storage, cookies, URLs, logs, or platform
requests. A reload deliberately requires discovery, a new grant, and bootstrap.

## Authenticated local request contract

The frozen transcript and header names are unchanged:

```text
METHOD | PATH | TIMESTAMP | NONCE | SHA256(RAW_BODY)
X-ZKD-Local-Session
X-ZKD-Timestamp
X-ZKD-Nonce
X-ZKD-MAC
X-ZKD-Protocol-Version
Origin
```

Use HMAC-SHA-256 with the memory-only session secret and transmit only the derived
MAC. Timestamp is decimal UTC epoch seconds. Every request and retry uses a fresh
nonce, timestamp, and MAC. Do not blindly retry ambiguous side-effecting uploads,
prepare/index, cancel, or future delete operations.

For JSON, serialize once to UTF-8 bytes, sign those exact bytes, and send those
same bytes. For PDFs, sign the original binary bytes and submit those same bytes;
never base64, normalize, convert to text, or rebuild a Blob after signing.

`tools/browser_protocol/browser_compute_reference.mjs` is a dependency-free Node
reference using browser-equivalent SHA-256/HMAC semantics. The Python reference and
tests are test material only and are not a frontend implementation.

## State and rebootstrap behavior

| Observed condition | Browser integration action |
| --- | --- |
| `READY`, no session | Request fresh grant and bootstrap |
| Valid local session, platform outage | Continue local request; do not poll platform per request |
| New session needed during platform outage | Cannot bootstrap; platform grant issuer is required |
| Session expiry/auth binding failure | Discard secret; rediscover then grant/bootstrap |
| Endpoint generation changed | Discard secret immediately; refresh discovery and bootstrap a fresh session |
| Device `OFFLINE` | Do not attempt content operation; wait for fresh `READY` discovery |
| `REVOKED` / `NOT_PAIRED` | Discard secret; no silent rebootstrap |
| `UPDATE_REQUIRED` | Discard secret; no downgrade or content operation |
| Temporary loopback failure | Refresh local/device state before any safe retry; never blindly repeat mutation |

## Future workflows

Documents: select PDF → ensure device/session → authenticated binary source upload
→ authenticated prepare → job/state reads → authenticated index → metadata-only
manifest sync → platform read model says queryable. PDF bytes, text, chunks,
embeddings, and evidence never transit the platform.

Ask: select a queryable device/document scope → ensure session → authenticated
`POST /v1/queries` or `/v1/answers` → local retrieval/context → local generation or
explicit user-funded direct provider call → answer/citations direct to browser.
`document_ids` is optional on the local query API; omitted means all queryable local
documents, supplied means that exact device-local subset. A document manifest on one
device does not imply usable content on another.

## Verification and limitations

`tests/fixtures/browser_compute_hmac_v1.json` contains safe empty, JSON-query,
JSON-answer, and binary-PDF-like vectors. It is verified by the browser-reference
algorithm and the Python Compute verifier. The isolated harness uses real platform
grant signing/consumption, local bootstrap, local PDF prepare/index/query, expiry
rebootstrap, endpoint generation change, offline discovery, outage continuity,
revocation, and update-required bootstrap denial.

Browser acceptance remains `BROWSER_ACCEPTANCE_NOT_EXECUTABLE`. This does not claim
Chrome/Edge PNA success. Authenticated real local generation remains
`AUTHENTICATED_LOCAL_GENERATION_NOT_EXECUTABLE` because the canonical Ollama model
was unavailable to the test environment; generation code was not changed.
