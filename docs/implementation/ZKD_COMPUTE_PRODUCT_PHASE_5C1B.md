# ZKD Compute Product Phase 5C.1B — Production Browser Compute Client Integration

## Scope and boundary

This phase adds only non-visual browser infrastructure in `frontend/src/compute/`. It does not activate local-first UI flows, change the Core RAG blocks, change the API or local service protocol, add a provider, persist secrets, or create a cloud fallback. Existing product visual files and CSS are intentionally outside this phase.

## Client contract

`BrowserComputeClient` discovers the authenticated owner’s platform device registry, selects an explicitly usable `READY` device, obtains a one-time platform grant, bootstraps `POST http://127.0.0.1:<port>/v1/sessions`, and keeps the returned session material in process memory only. The public `status()` result is redacted: it never contains the local session ID or HMAC key.

The Origin is always taken from `window.location.origin`; production therefore resolves to `https://rag.zkd.id.vn`, while development relies on the separately configured development allowlist. The browser client does not accept a caller-supplied production Origin.

The implementation uses only these current loopback routes:

| Operation | Route |
| --- | --- |
| Runtime/capability | `GET /v1/runtime`, `GET /v1/capabilities` |
| Source, prepare, state, index | `PUT /v1/documents/{id}/source`, `POST /prepare`, `GET /v1/documents/{id}`, `POST /index` |
| Job state/cancel | `GET /v1/jobs/{id}`, `POST /v1/jobs/{id}:cancel` |
| Retrieval/answer | `POST /v1/queries`, `POST /v1/answers` |

No browser delete, availability, ticketed accept, session-disconnect, or long-poll method is exposed because they are not present in the current production loopback API.

## Exact request proof

For every authenticated local request the client builds exactly:

```text
METHOD|PATH|TIMESTAMP|NONCE|SHA256(RAW_BODY)
```

Web Crypto SHA-256/HMAC-SHA-256 is used. JSON is `JSON.stringify`-ed exactly once and the resulting UTF-8 byte array is both signed and transmitted. Binary uploads are read as bytes and likewise signed/transmitted unchanged. The source uses only literal `http://127.0.0.1:<validated-port>` endpoints, never a hostname or arbitrary URL.

## Lifecycle and failure handling

- A valid in-memory session serves local requests without a per-request platform call.
- Session expiry, binding/auth failure, revoked pairing, `UPDATE_REQUIRED`, or changed endpoint generation clears the secret and fails closed.
- A caller can rediscover and explicitly bootstrap again; mutations are never blindly replayed.
- Multiple eligible devices require explicit selection; no implicit machine choice is made.
- Error handling exposes typed browser errors but never returns/logs grants, nonces, MACs, or session keys.

## Handoff examples

```ts
const compute = new BrowserComputeClient();
await compute.discover();
await compute.selectDevice("documents", selectedDeviceId);
await compute.ensureSession("documents");
await compute.runtime();
await compute.uploadSource(documentId, file, file.name);
await compute.prepareDocument(documentId);
```

```ts
await compute.selectDevice("retrieval", selectedDeviceId);
const result = await compute.query({ query_text, document_ids: [documentId] });
const answer = await compute.answer({ query_text, document_ids: [documentId] });
compute.logout();
```

The future Documents local-first phase owns UI state, device picker UX, progress polling, and user-facing error copy. It must not persist `BrowserComputeClient` session material.

## Verification scope

`frontend/src/compute/crypto.test.ts` executes all frozen `browser_compute_hmac_v1.json` vectors, including JSON and binary bodies. `client.test.ts` covers bootstrap, redacted session state, signed local use without an extra platform request, explicit multi-device selection, endpoint-change invalidation, and session-expiry fail-closed behavior.

`BROWSER_ACCEPTANCE_NOT_EXECUTABLE`: this implementation does not claim real Chrome/Edge CORS/PNA acceptance. `AUTHENTICATED_LOCAL_GENERATION_NOT_EXECUTABLE`: no real model generation was executed in this phase.
