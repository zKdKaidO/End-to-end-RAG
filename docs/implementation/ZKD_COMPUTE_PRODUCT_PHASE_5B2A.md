# ZKD Compute Product Phase 5B.2A — Platform-Signed Local Session Grants

## Scope and reused session design

This phase replaces only the P2C.4A development grant-bootstrap placeholder.
The existing memory-only `LocalSessionManager` and its per-request HMAC
validation are retained; P2C.5B.2B will extend enforcement uniformly across
sensitive endpoints. No frontend, browser workaround, or RAG semantics are
included.

## Trust anchor and grant format

`PlatformGrantVerificationKeyProvider` accepts only trusted installed/configured
platform Ed25519 public verification material. It never accepts a browser key
or a key embedded in the grant and fails closed if unavailable. Grants use the
exact P2C.5A signed format and claims: `grant_id`, `user_id`, `device_id`,
`credential_epoch`, `endpoint_generation`, `origin`, `browser_nonce`,
`operations`, and `exp`.

## Verification and consumption order

The local route `POST /v1/sessions` validates: request origin; platform
signature; local paired device/account; credential epoch; endpoint generation;
browser nonce; expiry; and the fail-closed operation allowlist. It then creates
random session bootstrap material and atomically inserts only a SHA-256 grant-ID
replay record into catalog SQLite. A unique key makes concurrent consumption
single-winner. Expired replay records are removed before insert; valid grants
cannot be replayed while their expiry record remains.

## Session model

The returned bootstrap includes opaque session ID, random memory-only session
secret, expiry, operation set, protocol version, and endpoint generation. The
secret, full grant, signature, and browser nonce are never persisted or logged.
Sessions bind to user, device, epoch, endpoint generation, origin, nonce, and
permissions. Runtime restart clears sessions; endpoint generation recreation
invalidates sessions; revocation and `UPDATE_REQUIRED` invalidate them
fail-closed.

## Offline property and limits

Verification is local and needs no platform request after the browser has a
valid grant. Known local revocation overrides a valid grant. Platform key
rotation, an OS production credential store, browser acceptance, custom URI,
and installer work remain deferred.

## Verification

Focused tests use the real P2C.5A issuer/verifier path plus temporary device
identity and local root: signed grant acceptance, durable one-time replay
rejection, nonce mismatch rejection, no secret persistence, platform-control
regression, and local-runtime/RAG regression. Browser status remains
`BROWSER_ACCEPTANCE_NOT_EXECUTABLE`.

Next: **P2C.5B.2B AUTHENTICATED LOCAL REQUEST ENVELOPE**.
