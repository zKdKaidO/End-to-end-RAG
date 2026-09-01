# ZKD Compute Product Phase 5B2B — Authenticated Local Request Envelope

## Scope

P2C.5B.2B closes the browser-to-loopback request-authentication gap without changing
the frozen P2C.4A protocol, Core RAG behavior, provider routing, or browser-facing
API semantics. It applies the existing per-session HMAC request proof to every
sensitive local Compute route after the existing platform-issued grant has created a
memory-only local session.

`/health`, CORS preflight, and the one-time `/v1/sessions` grant exchange are the
only unauthenticated loopback endpoints. The grant exchange remains protected by the
P2C.5B.2A signed platform grant, origin validation, browser nonce, expiry, replay
prevention, paired device identity, credential epoch, and endpoint generation.

## Canonical request proof

This phase reuses the P2C.4A transcript exactly; it does not introduce a second
request-signing scheme:

```text
METHOD | EXACT_PATH | TIMESTAMP | NONCE | SHA256(RAW_BODY)
```

The browser sends the existing headers:

```text
X-ZKD-Local-Session
X-ZKD-Timestamp
X-ZKD-Nonce
X-ZKD-MAC
X-ZKD-Protocol-Version
```

`X-ZKD-MAC` is HMAC-SHA-256 over the canonical transcript using the memory-only
session key. The session identifier is cryptographically bound through lookup of its
unique session key: substituting a different session identifier selects a different
key and invalidates the MAC. The parser verifies the exact method, exact path, raw
body hash, timestamp window, origin, and one-use nonce. The nonce check and nonce
recording are protected by one session-manager lock, so concurrent replays cannot
both pass.

The implementation exposes one shared `canonical_request_transcript` / `request_mac`
helper. This keeps test proof generation aligned with the server verifier; protocol
serialization remains unchanged.

## Sensitive-route operation map

The local API owns a centralized method/path-to-grant-operation map. It denies an
unknown sensitive route and checks the map before the route's domain work begins.

| Route family | Required grant operation |
| --- | --- |
| runtime and capabilities; job read/cancel | `jobs` |
| binary probe; document source, prepare, state, and index | `documents` |
| document-set query | `retrieval` |
| document-set answer | `answer` |

Platform-issued grant operations are enforced for bound sessions. Explicit
development-bootstrap sessions retain the established unrestricted test-only behavior
when no operation list is present; production does not use that bootstrap path.

## Route classification and coverage

| Classification | Routes |
| --- | --- |
| `PUBLIC_SAFE` | `GET /health`; permitted CORS/PNA `OPTIONS` preflight only |
| `GRANT_BOOTSTRAP` | `POST /v1/sessions`, protected by the P2C.5B.2A platform grant and browser nonce |
| `SESSION_AUTH_REQUIRED` | `GET /v1/runtime`, `GET /v1/capabilities`, `POST /v1/probe/binary`, `PUT /v1/documents/{document_id}/source`, `POST /v1/documents/{document_id}/prepare`, `GET /v1/documents/{document_id}`, `POST /v1/documents/{document_id}/index`, `GET /v1/jobs/{job_id}`, `POST /v1/jobs/{job_id}:cancel`, `POST /v1/queries`, and `POST /v1/answers` |
| `DEVICE_INTERNAL` | catalog, source storage, preparation, indexing, retrieval, provider routing, and control-channel services; none are browser routes |

There is no local document-delete or browser long-poll endpoint in the current
frozen loopback API, so this phase does not introduce either. Any future sensitive
route must be added to `ROUTE_OPERATIONS` before it can be accepted.

## Binary upload handling

The source-upload route authenticates its raw body before constructing
`LocalDocumentStore` or writing a document. The body is read once through Starlette's
request cache so the bytes hashed by authentication are the same bytes passed to the
store. The existing 10 MiB `source_pdf_max_bytes` bound applies to source uploads;
the ordinary request bound continues to apply elsewhere. This phase does not alter
PDF validation, storage format, preparation, indexing, or document semantics.

## Session and device invalidation

In addition to HMAC validation, a bound session must still match the current paired
device ID, credential epoch, and endpoint generation. Update-required and revocation
states invalidate sessions. The runtime then fails closed; it does not allow a
previously authenticated browser session to continue using local document, retrieval,
or generation routes.

Session expiry and timestamp skew are enforced before domain work. A mismatched
protocol version transitions the runtime to `UPDATE_REQUIRED` and clears sessions.
The local session manager holds replay check-and-consume in one lock. This preserves
the memory-only replay ledger while ensuring two concurrent requests bearing the
same nonce cannot both succeed.

## Local-first availability, privacy, and logging

No sensitive request calls the platform for per-request authorization. A valid local
session continues to use local document/retrieval services if the control transport
is temporarily unavailable; a later observed revocation fails subsequent requests
closed. Browser HMAC remains distinct from the device Ed25519 control-channel
identity. User-cloud routing is unchanged: if separately selected it remains a
direct device-to-user-provider path, never a platform relay.

The local audit log retains request ID, HTTP operation, status, and duration only.
It does not write session keys, MACs, browser nonces, raw queries, PDFs, prompts,
or provider credentials.

## Verification

Focused coverage in `tests/unit/local_compute/test_runtime.py` and
`tests/integration/test_local_compute_control_channel.py` verifies:

- valid raw binary request proof;
- replay rejection;
- invalid MAC rejection;
- operation authorization rejection;
- paired-device epoch binding rejection; and
- revocation invalidation of an authenticated session.

The isolated synthetic protocol E2E additionally verifies a real local PDF source
acceptance, preparation, E5 indexing, retrieval, document-state read, local query
during control-plane outage, and observed-platform-revocation fail-closed behavior.
`POST /v1/answers` is protected by the same map but its real-model E2E remains
separately opt-in because no configured local Ollama model was available during this
verification.

The browser acceptance gate remains `BROWSER_ACCEPTANCE_NOT_EXECUTABLE`; this phase
does not add an insecure browser workaround. Browser-side HMAC/session integration,
custom URI pairing, OS credential-store production hardening, desktop packaging, and
platform verification-key rotation remain future work in P2C.5C or later phases.
