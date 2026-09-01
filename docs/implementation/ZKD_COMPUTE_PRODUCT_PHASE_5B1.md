# ZKD Compute Product Phase 5B.1 — Outbound Control Channel

## Scope

P2C.5B.1 adds only the outbound, metadata-only `ZKD Compute → Platform`
control channel. It does not add browser-to-loopback transport, local-session
grant consumption, frontend changes, platform compute, or RAG semantics.

## Identity and paired state

The device uses an Ed25519 identity. Private key access is behind
`DeviceCredentialStore`; the production default is fail-closed until an
OS-protected key-store backend is supplied. `TemporaryFileDeviceCredentialStore`
is explicitly test/development-only. SQLite stores only non-secret paired state:
device/account identity, credential epoch, platform endpoint, protocol version,
pairing state, and revocation state.

## PlatformControlClient and signing

`PlatformControlClient` exposes only signed presence and metadata-manifest
operations. It uses the exact P2C.5A transcript:
`METHOD|PATH|EPOCH|TIMESTAMP|NONCE|SHA256(BODY)`. Request JSON is serialized
once, deterministically, and those same bytes are signed and sent. A fresh
cryptographic nonce is created for each call. The client has no generic product
HTTP interface.

## Presence and control state

`ControlChannel` tracks `DISCONNECTED`, `CONNECTING`, `CONNECTED`,
`BACKING_OFF`, `REVOKED`, and `UPDATE_REQUIRED` independently of local document
state. Presence reports only frozen state/version/endpoint-generation/port,
capability admission, and safe provider state. It reports neither local paths,
content, prompts, credentials, nor private keys. Retry uses bounded exponential
backoff with injected clock/jitter seams; a successful call resets it.

## Manifest outbox

Catalog schema v3 adds a coalescing `control_manifest_outbox`. Each document
has at most one current pending row; replacing metadata increments its revision,
so newer state wins and a successful acknowledgement marks it delivered. The
outbox accepts only the P2C.5A allowlist and rejects forbidden content before
SQLite persistence, serialization, or logging. Control outage leaves all local
documents, artifacts, indexes, and pending metadata intact.

## Revocation and compatibility

`DEVICE_REVOKED` or credential-auth/epoch rejection moves the control channel
and runtime to `REVOKED`, stopping subsequent writes without deleting local data.
Protocol incompatibility moves the runtime to `UPDATE_REQUIRED`; no downgrade or
unsigned update path exists.

## Verification

The isolated E2E uses a temporary data root/key store and the real P2C.5A
service verifier: pairing proof and confirmation, signed READY presence,
metadata-only manifest delivery, outage persistence/recovery, platform
read-model persistence, and revocation. Focused control, platform, and local
runtime tests pass. Browser acceptance remains
`BROWSER_ACCEPTANCE_NOT_EXECUTABLE`.

## Limitations and next phase

The platform transport adapter is an injectable control boundary; packaged TLS
transport, OS-protected key storage, reconnect host lifecycle, and desktop
packaging are still pending. Grant verification/one-time consumption and browser
session creation are deliberately deferred to **P2C.5B.2 LOCAL SESSION GRANT
CONSUMPTION + BROWSER SESSION FOUNDATION**.
