# BROWSER_COMPUTE_PROTOCOL_V1

**Project:** ZKD / Vietnamese Legal RAG
**Status:** **ACTIVE V1 BROWSER/COMPUTE PROTOCOL**
**Decision date:** 2026-09-01
**Depends on:** `LOCAL_FIRST_COMPUTE_ARCHITECTURE_V1.md` and `LOCAL_DATA_RUNTIME_CONTRACT_V1.md`
**Scope:** Trust model and versioned protocol between the public browser, platform control shell, and local ZKD Compute

---

## 1. Scope and non-goals

This contract freezes the Browser-to-ZKD Compute V1 protocol design. It does not implement a desktop application, browser UI, local service, cloud control endpoints, installer, updater, LocalStoreV1 adapter, or a UserCloudComputeProvider. It does not alter frozen Blocks 1–6, frontend code, canonical development data, Cloudflare/DNS, Terraform, or historical cloud infrastructure.

The protocol preserves the active local-first rule: a compatible local provider must be READY before upload; raw PDFs and RAG content stay local; and the web shell remains useful with compute offline.

## 2. Three channels and content boundary

| Channel | Permitted purpose | Prohibited content |
|---|---|---|
| Browser ↔ Platform Cloud | Account authentication, device selection/registry, pairing orchestration, local-session grants, lightweight manifests, UI control state | Raw PDFs, pages, chunks, embeddings, indexes, retrieval evidence, context, document-derived prompts, or answer/citation content by default |
| ZKD Compute ↔ Platform Cloud | Outbound device registration/presence, capabilities, revocation, version policy, metadata-only manifest outbox | The same document/RAG content above; this is never a hidden document relay |
| Browser ↔ ZKD Compute local data channel | Direct PDF transfer, local document/job operations, content-dependent query, local progress, answer/citation results | Cloud credentials, arbitrary filesystem paths, arbitrary commands, other-user/device content |

The browser receives the local endpoint descriptor only after an authenticated platform device-selection request. Content traffic never passes through the platform as a convenience relay.

## 3. Transport candidates

| Candidate | Strengths | Material risk/limitation | Decision |
|---|---|---|---|
| Loopback HTTP | Native Chrome/Edge support, direct streaming, no certificate UX, simple request/response | Requires exact CORS/PNA handling and dedicated local authentication | **Selected for data/jobs.** |
| Loopback HTTPS | Encrypted loopback endpoint | Publicly trusted cert is not practical for a per-device loopback endpoint; a local trust root adds installer/enterprise-policy complexity | Not V1. |
| Loopback WebSocket/WSS | Push progress | Adds origin-hijacking and HTTPS/loopback compatibility surface; not needed when durable state supports polling | Not V1 primary transport. |
| Custom URI/deep link | Normal installed-app discovery and foreground/launch UX | Not suitable for binary data or general requests | **Selected only for launch/pairing.** |
| Browser extension | Can mediate native access | Separate browser installation, review/update scope, and browser-family dependence | Rejected for V1. |
| Cloud-relayed content channel | Could avoid local CORS | Violates the no-platform-document-relay invariant | Rejected. |
| OS native IPC alone | Good desktop-internal boundary | A website cannot directly use it without an extension/native bridge | Used internally by Compute only, not browser transport. |

Loopback addresses are treated as potentially trustworthy by the Secure Contexts specification, but this does not make localhost callers trusted. Chrome's Private Network Access direction requires explicit opt-in/preflight behavior for local/private endpoints, so V1 implements the required CORS/PNA response policy rather than relying on a browser exception. [W3C Secure Contexts](https://www.w3.org/TR/secure-contexts/), [Chrome Private Network Access](https://developer.chrome.com/blog/private-network-access-preflight?hl=en)

## 4. Selected V1 transport, binding, and discovery

The selected composition is:

```text
Browser -- HTTPS --> Platform control shell
Browser -- zkd-compute:// --> installed companion (launch/pair only)
Browser -- authenticated HTTP/CORS --> 127.0.0.1:<ephemeral-port> ZKD Compute
ZKD Compute -- outbound authenticated TLS --> Platform control shell
```

ZKD Compute binds its protocol listener only to literal IPv4 loopback `127.0.0.1`. It does not bind `0.0.0.0`, any LAN address, `localhost` DNS name, or a public interface. IPv6 `::1` support is deliberately deferred until it has the same origin/PNA/security test matrix; the browser uses the literal IPv4 endpoint in V1.

At each runtime start, Compute selects an OS-assigned ephemeral port, records it only locally, and reports an endpoint descriptor (`device_id`, endpoint generation, port, protocol version, availability) through its authenticated outbound platform presence channel. The platform returns that descriptor only to the authenticated owner selecting that device. This avoids a globally predictable unauthenticated service. A port collision is handled by rebinding to a new OS-assigned port and publishing a new endpoint generation; stale descriptors are rejected.

`zkd-compute://open` may launch or foreground the installed companion. `zkd-compute://pair?request_id=<opaque-id>` may initiate pairing. The URI contains no document bytes, filesystem path, permanent credential, arbitrary command, executable URL, or general operation argument.

## 5. Trust model and threat boundary

Loopback is a network-placement constraint, not authorization. Every sensitive local request requires exact origin validation, a valid local session, freshness/MAC verification, device/account binding, operation scope, and document/job ownership checks.

| Threat | Required mitigation |
|---|---|
| Malicious website, iframe, CSRF, cross-origin fetch | Exact allowlist; no wildcard/reflection; CORS/PNA preflight; local session and MAC required; framing protections on web shell. |
| DNS rebinding/LAN exposure | Literal `127.0.0.1` binding and browser target; no hostname/LAN bind; origin/PNA checks. |
| Stolen platform browser session | Cloud issues short-lived, device/account/origin-bound local grants; local service does not accept platform cookies. |
| Stolen local-session material | Memory-only, short-lived session; per-request nonce/timestamp/MAC; expiry and revocation. |
| Pairing replay/device impersonation | One-time, user/account-bound challenge; local user confirmation; locally generated device key; platform redemption record. |
| WebSocket hijacking | V1 avoids WebSocket as the primary event channel; future use must validate Origin and one-time event ticket. |
| Arbitrary path/path traversal | Protocol accepts browser-selected bytes only; no `read_path`/`write_path`; all writes resolved under managed data root. |
| Oversized upload/resource exhaustion | Streaming size enforcement, configured request/job/concurrency bounds, cancellation, durable admission. |
| Job-ID guessing/cross-user access | Opaque UUIDs plus authenticated owner/device/session and local-artifact availability checks. |
| Revoked/stale device or tab | Revocation epoch invalidates sessions; cloud refuses new grants; endpoint generation and session expiry reject stale tabs. |
| Downgrade/version mismatch | Explicit protocol/runtime/artifact negotiation; `UPDATE_REQUIRED`; no silent fallback. |

The protocol does not claim to protect against malware with the same user privileges, a compromised browser process, or a fully compromised host. Loopback HTTP is acceptable only because it never leaves the host network stack and all sensitive operations have an independent cryptographic local-session check.

## 6. Pairing and device identity

Pairing is user-visible but needs no copied API key, configuration edit, port entry, or terminal.

1. Authenticated user clicks **Connect this computer** on the web shell.
2. Browser asks platform for a short-lived, one-time `pairing_request_id`, bound to account, browser session, intended product origin, and expiry.
3. Browser invokes `zkd-compute://pair?request_id=<opaque-id>`; the companion launches/foregrounds.
4. Compute generates an Ed25519 device keypair locally and stores the private key with OS-protected credential storage. It contacts the platform over TLS using the one-time pairing request.
5. Web and companion display the same short confirmation code/account label; the user confirms in Compute. The code is rate-limited and expires with the pairing request.
6. Platform records `device_id` and public key, marks the request consumed, and returns a revocable device credential record. Compute proves the device key on future cloud connections and receives short-lived device access tokens, never a universal permanent bearer token.
7. Browser observes completion through its authenticated cloud session, then requests a dedicated local-session grant for the selected device.

`device_id` is an opaque stable UUID. The local private key is device-bound, rotatable/revocable through platform credential version/epoch, and is never exposed to browser JavaScript. Pairing challenges and confirmation codes are short-lived and one-time. Platform browser sessions, cloud device tokens, and browser-local sessions are separate credentials.

## 7. Local-session and origin policy

After pairing, the browser asks the platform for a one-time signed `local_access_grant`, scoped to the authenticated account, selected `device_id`, endpoint generation, exact product origin, allowed operations, and a browser-generated binding nonce. The grant has a short configurable lifetime and contains no document content.

Browser sends the grant to `POST /v1/sessions` on the selected loopback endpoint. Compute verifies the platform signature, expiry, endpoint generation, device revocation epoch, exact `Origin`, and one-time grant ID. It consumes the grant in `catalog.sqlite3` and returns an opaque `local_session_id` plus random session key. Browser keeps both in memory only, never in localStorage or a persistent cookie.

Every later state-changing/sensitive request supplies:

```text
X-ZKD-Local-Session
X-ZKD-Timestamp
X-ZKD-Nonce
X-ZKD-MAC = HMAC(session_key, method || path || timestamp || nonce || body_hash)
```

Compute rejects expired timestamps, reused nonces, invalid MACs, wrong origin, wrong endpoint generation, account/device mismatch, revoked devices, and out-of-scope operations. A browser refresh obtains a new cloud grant and local session automatically. Existing sessions expire quickly by policy; no new session is created while cloud authorization is unreachable.

Production allows only `https://rag.zkd.id.vn`. Development origins are an explicit opt-in, separately packaged/configured allowlist (for example the local frontend development origin), visibly marked as development, and cannot be enabled accidentally in a production package. No `Access-Control-Allow-Origin: *`, arbitrary origin reflection, or platform-cookie reuse is permitted.

The listener answers CORS preflight only for exact allowed origin, methods, and headers. When a browser sends `Access-Control-Request-Private-Network: true`, the allowed preflight also returns `Access-Control-Allow-Private-Network: true`; all other origins receive a generic denial. Final authenticated responses use the same exact `Access-Control-Allow-Origin` policy. This anticipates PNA enforcement without asking users to disable protections. [Chrome PNA preflight guidance](https://developer.chrome.com/blog/private-network-access-preflight?hl=en)

## 8. Direct PDF transfer and file authorization

The local PDF flow is strictly:

```text
Browser File object/stream
  -> authenticated loopback upload ticket
  -> 127.0.0.1 ZKD Compute
  -> managed temporary file
  -> Block 1 validation + SHA-256 + dedupe
  -> atomic managed source copy
```

The platform only issued an opaque logical `document_id`/local-session grant; it does not see or relay bytes. Browser provides selected bytes, never a host path. Compute exposes no `read_file`, `read_path`, `write_path`, `execute_command`, shell, Python, or generic operation endpoint.

`accept_document` first creates a one-time upload ticket bound to local session, document ID, idempotency key, allowed size policy, filename metadata, and expiry. `PUT /v1/uploads/{ticket}` accepts `application/pdf` bytes as a stream. If `Content-Length` is present it is checked before reading; byte count is enforced while streaming regardless, so the browser need not retain the whole PDF in memory. Compute validates magic/MIME/structure, calculates SHA-256, supports cancellation, writes only under its `tmp` then managed document root, and applies P2C.2 duplicate/atomic-acceptance rules.

## 9. Protocol schema and typed errors

All JSON request bodies include `protocol_version`; every mutating request also includes an `idempotency_key`. Responses contain `request_id`, `device_id`, endpoint generation, and typed status/error metadata. IDs are opaque UUIDs; no route accepts filesystem paths.

| Operation | Local route/method | Auth/content | Idempotency and output |
|---|---|---|---|
| `get_runtime_info` | `GET /v1/runtime` | Local session; no content | Read-only runtime/protocol/profile/primary state. |
| `get_capabilities` | `GET /v1/capabilities` | Local session; no content | Read-only admitted capabilities and coarse availability only. |
| `create_local_session` | `POST /v1/sessions` | Exact Origin + one-time cloud grant; no content | One-time grant consumption; returns memory-only session material. |
| `accept_document` | `POST /v1/documents/accept` then `PUT /v1/uploads/{ticket}` | Session/MAC then one-time upload ticket; **PDF bytes local only** | Key maps to one ticket/result; returns acceptance/document state. |
| `prepare_document` | `POST /v1/documents/{id}/prepare` | Session/MAC; no content | Key maps to one local job. |
| `get_document_state` | `GET /v1/documents/{id}` | Session/MAC; metadata only | Read-only local state/availability. |
| `list_local_availability` | `POST /v1/documents:availability` | Session/MAC; metadata only | Batch local availability for supplied opaque IDs. |
| `query_document_set` | `POST /v1/queries` | Session/MAC; local query/result content | Returns direct local Block 4–6 result; no cloud relay. |
| `cancel_job` | `POST /v1/jobs/{id}:cancel` | Session/MAC; no content | Idempotent cancellation request/status. |
| `delete_document` | `DELETE /v1/documents/{id}` | Session/MAC; no content | Durable local deletion/tombstone job. |
| `get_job_state` | `GET /v1/jobs/{id}` | Session/MAC; metadata only | Durable stage/progress/typed error/result reference. |
| `subscribe_job_events` | `POST /v1/jobs/{id}:poll` | Session/MAC; metadata only | Long-poll cursor; returns ordered durable events, not the sole truth. |
| `disconnect_session` | `POST /v1/sessions/{id}:disconnect` | Session/MAC; no content | Idempotently invalidates browser local session. |

Stable product-facing error codes include: `COMPUTE_OFFLINE`, `NOT_PAIRED`, `SESSION_EXPIRED`, `DEVICE_REVOKED`, `ORIGIN_NOT_ALLOWED`, `CAPABILITY_UNAVAILABLE`, `DOCUMENT_NOT_LOCAL`, `ARTIFACT_INCOMPATIBLE`, `DOCUMENT_BUSY`, `INVALID_PDF`, `PDF_TOO_LARGE`, `JOB_NOT_FOUND`, `JOB_CANCELLED`, `UPDATE_REQUIRED`, `LOCAL_STORAGE_ERROR`, `MODEL_UNAVAILABLE`, `IDEMPOTENCY_CONFLICT`, and `INTERNAL_COMPUTE_ERROR`. Normal responses never expose tracebacks, raw paths, secrets, or document content through errors.

## 10. Capabilities, states, and jobs

Capabilities are `pdf_processing`, `chunking`, `embedding`, `indexing`, `retrieval`, and `generation`. Authenticated capability responses expose only capability availability/admission, busy state, runtime/protocol/artifact-contract versions, model readiness, and optionally a coarse resource class. They do not expose serial numbers, exact GPU fingerprints, filesystem locations, or process topology.

Primary runtime states are mutually exclusive:

| State | Meaning and browser consequence |
|---|---|
| `OFFLINE` | No current platform presence/local endpoint; show Connect/Open CTA; no Upload/Ask. |
| `CONNECTING` | Companion is establishing outbound control connection; no admission. |
| `AUTHENTICATING` | Device credential/protocol validation in progress; no admission. |
| `READY` | Compatible, healthy, and admits declared capabilities. |
| `BUSY` | At local policy concurrency limit; show progress and do not over-admit. |
| `DEGRADED` | Reachable but only a declared subset is currently admitted; UI evaluates capability-by-capability. |
| `UNAVAILABLE` | No capability can safely admit work (resource/model/storage failure). |
| `REVOKED` | Device credential invalidated; all sessions/jobs admission stopped. |
| `UPDATE_REQUIRED` | Protocol/artifact policy incompatible; no affected operation proceeds. |

Jobs use durable LocalJobStore states `QUEUED`, `RUNNING`, `CANCEL_REQUESTED`, `SUCCEEDED`, `FAILED`, and `CANCELLED`. Job records include job/account/device IDs, operation, document IDs, artifact ID when relevant, stage/progress, cancellation status, timestamps, typed error, and result metadata. Terminal states are immutable. Cancellation is best-effort at safe boundaries; a request received during atomic artifact promotion is recorded and resolved safely rather than promising an unsafe immediate stop.

Same authenticated `idempotency_key` + operation + body hash resolves to the original job/result within its retained scope. A reused key with different content returns `IDEMPOTENCY_CONFLICT`; browser retry cannot create duplicate preparation/deletion/upload work.

## 11. Progress, reconnect, and cloud presence

V1 selects authenticated long-polling from durable local job state over WebSocket/SSE. `subscribe_job_events` returns ordered state changes such as Receiving, Processing, Chunking, Indexing, Ready, failure, and cancellation. Browser refresh/reopen recreates its local session and resumes from an event cursor or `get_job_state`; events are an optimization, never sole source of truth.

| Condition | Required behavior |
|---|---|
| Browser refresh/close | Local job continues; fresh browser session polls durable job state. |
| Compute restart | Device key, catalog, active artifact, and job records reconcile; unfinished work never becomes READY without validation. |
| Sleep/wake/local-channel loss | Existing local job follows durable scheduler policy; browser reconnects via fresh local session/endpoint descriptor. |
| Temporary platform outage | Existing local artifact and running job survive; existing short-lived local session may finish admitted work; new pairing/grants and manifest acknowledgements wait for cloud recovery. |
| Runtime shutdown during job | Durable job becomes interrupted/failed or safely cancelled; staged artifact is never promoted without validation. |

Compute maintains an outbound authenticated TLS connection or reconnecting request channel to cloud for device presence, states/capabilities, revocation epoch, version policy, and manifest outbox acknowledgement. It uses exponential backoff with jitter. It carries no document content.

After local actions, durable outbox events include `DOCUMENT_ACCEPTED`, `PREPARATION_STARTED`, `PREPARATION_READY`, `PREPARATION_FAILED`, `LOCAL_ARTIFACT_MISSING`, and `DOCUMENT_DELETED_LOCAL`. Payloads are constrained to P2C.2 metadata. Delivery is at-least-once with event IDs; platform acknowledgement is idempotent and Compute retries until acknowledged. No cloud manifest grants browser access to local content.

## 12. Routing, query/result, versions, and resource protection

Provider selection requires account ownership, device `READY`/admitted capability, selected document local availability on that exact device, and artifact compatibility. A document only on Device A is never routed to Device B merely because B is READY; V1 has no automatic cross-device transfer.

Local Ask is:

```text
Browser -> authenticated local query -> ZKD Compute
 -> E5 query embedding -> local dense/lexical/RRF/hierarchy/context
 -> local or explicitly user-funded generation provider
 -> structured Block 6 answer/citations -> Browser
```

The answer and citation result return directly from Compute to Browser. The platform receives neither evidence/context nor answer text by default. A user-funded external generation provider remains a later explicit data-transfer contract.

Protocol negotiation covers `protocol_version`, runtime version, supported min/max versions, artifact-contract version, endpoint generation, and device revocation epoch. Incompatible peers enter `UPDATE_REQUIRED`; no silent downgrade. Future updates require signed trusted releases, and the protocol never accepts executable payloads or arbitrary update URLs.

Resource protection is configuration/policy driven: existing PDF size/structure limits are enforced; request bodies are bounded; upload tickets expire; local sessions have bounded lifetime; request and polling rates are limited; local queue/concurrency limits and durable cancellation prevent unbounded work. The protocol does not invent enterprise-scale numeric limits or expose internal worker control to the browser.

Local logs record IDs, operation/state transitions, durations, endpoint generation, capability decisions, and typed errors. They must redact PDF/chunk/evidence/prompt content, answers, session keys, grants, device credentials, raw headers, and managed paths by default. Sensitive diagnostics require explicit local support consent.

## 13. Acceptance plans and implementation boundaries

Security acceptance tests for implementation must verify:

- legitimate `https://rag.zkd.id.vn` local-session request succeeds;
- random website, iframe, wrong Origin, missing/expired session, and PNA/CORS denial fail;
- revoked device and replayed pairing/local grant fail;
- arbitrary path/command operations do not exist; oversized streaming upload is rejected;
- job/document ownership is enforced; Device B cannot query Device A-only content;
- platform outage never relays/leaks content; version mismatch enters `UPDATE_REQUIRED`.

Product acceptance tests must verify:

- install -> Connect this computer -> pair -> READY without terminal work;
- restart/autostart/reconnect returns READY without re-pairing;
- offline shell shows manifest but disables Upload/Ask;
- ready device enables Upload; selected PDF transfers locally, progresses, and becomes READY;
- browser refresh during indexing resumes durable progress; device restart reconciles state;
- local Ask returns structured answer/citations; revoke removes availability.

Implementation should map to concrete boundaries already identified by P2C.2:

| Future component | Concrete responsibility |
|---|---|
| ZKD Compute control service/local protocol server | Loopback listener, CORS/PNA/origin enforcement, operation dispatch. |
| Pairing manager/device identity manager | Custom-URI pairing, Ed25519 key, OS credential storage, revocation/version proof. |
| Local session manager | Grant verification, memory-only sessions, nonce/MAC replay defense. |
| ComputeRuntime/capability manager | State machine, admission, endpoint descriptor, resource policy. |
| LocalJobStore/scheduler | Durable jobs, idempotency, cancellation, polling events, restart recovery. |
| DocumentStore/ArtifactStore/LocalRetrievalStore | P2C.2 source/artifact lifecycle and Blocks 1–6 localization. |
| ManifestSyncClient/outbox | Outbound-only, metadata-only platform synchronization. |

## 14. Transport evidence and remaining decisions

No browser security setting was weakened and no prototype touched production/frontend/canonical data. A narrow in-app-browser prototype was attempted, but the supplied browser-control runtime could not initialize in this host because its package imports `node:process`, which the available Node execution environment blocks. No substitute browser automation or insecure browser flag was used.

The selected design therefore treats PNA/CORS behavior as an explicit implementation acceptance gate, not an assumed exception. Before a desktop MVP is released, the team must run the stated synthetic-byte probe in supported Chrome and Edge versions from `https://rag.zkd.id.vn`-equivalent HTTPS origin: exact CORS/PNA preflight, binary stream upload, polling/reconnect, refresh, denied foreign origin, and no insecure flags. This does not block the V1 protocol decision because the service design includes the required browser opt-in and has a safe failure mode: no valid local session means no content access.

Open decisions remain: desktop packaging/installer/code-signing/updater; final cloud-shell control endpoints; production browser test matrix; UserCloudComputeProvider data-transfer protocol; manifest service implementation; and later IPv6 loopback support.

---

```text
BROWSER_COMPUTE_PROTOCOL_V1
STATUS: ACTIVE V1 BROWSER/COMPUTE PROTOCOL
```
