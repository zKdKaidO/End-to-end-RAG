# ZKD Compute Product Phase 5A — Platform Control Plane

## Scope and channel boundary

This additive phase implements platform metadata/control records only. Browser
to platform handles authenticated device registry, pairing, grants and manifest
read models. Compute to platform handles signed presence and metadata manifest
upserts. Browser-to-loopback transport, PDF/RAG work, frontend, and provider UI
remain deferred.

## Identity, pairing, and device authentication

`compute_devices` stores only an Ed25519 public key, owner, credential epoch,
versions, and revocation metadata. Pairing challenges store hashes of a random
one-time token and six-digit human confirmation code with a short expiry.
Compute proves private-key possession by signing the pairing transcript; the
owner separately confirms the code. Device requests sign method, path, epoch,
timestamp, nonce and body hash. Replayed nonces are persisted only until the
bounded authentication window.

Revocation records a timestamp and increments the credential epoch. New grants,
presence, and manifests then fail closed. Presence stores only state, versions,
literal-loopback discovery port/generation, capability metadata and last seen;
stale presence derives `OFFLINE`.

## Metadata privacy and grants

`local_document_manifests` is separate from the existing content tables and
contains only owner/device/document identity, filename/size, local lifecycle,
artifact compatibility and safe error metadata. It rejects PDF, text, chunks,
embeddings, prompts, context, answers, credentials and private keys. The
read model derives `queryable` only when the device is fresh and `READY`, the
retrieval capability is admitted, and the device-scoped manifest is READY,
AVAILABLE and artifact-compatible.

Grants are short-lived Ed25519-signed opaque claim payloads bound to owner,
device, credential epoch, endpoint generation, exact origin, browser nonce,
grant ID, expiry, and allowed operation scope. The companion can verify them
using the platform public key without receiving platform signing material. The
platform stores grant metadata, never raw device private material. Production
fails closed when no base64 Ed25519 signing key is configured. P2C.5B will
implement device verification and one-time consumption.

## APIs and verification

Browser-authenticated APIs cover pairing creation/confirmation, device list,
revocation, grant issuance and manifest listing. Device-authenticated APIs are
separate `/control/*` endpoints for pairing proof, presence and manifests.
They do not accept browser cookies as device proof.

Focused tests cover proof/confirmation, expiry/protocol rejection, replay
rejection, ownership isolation, revocation, presence, Ed25519 grant
verification/tamper rejection, manifest queryability/upsert and forbidden
content. Browser and device routes use different authentication boundaries.
The browser gate remains `BROWSER_ACCEPTANCE_NOT_EXECUTABLE`.

## Limitations and next phase

No browser-to-localhost flow, custom URI, desktop key storage, reconnect
worker, manifest outbox, or grant consumption is included. Next:
`P2C.5B ZKD COMPUTE CONTROL CHANNEL + LOCAL SESSION GRANT CONSUMPTION`.
