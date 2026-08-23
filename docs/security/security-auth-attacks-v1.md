# Authentication Attacks V1

## Red team

Eight rapid invalid logins all reached password verification and returned `401`; no request was throttled. Observed elapsed times were 187, 55, 53, 54, 57, 56, 66 and 61 ms. Invalid user/password responses remained uniform, so account enumeration was not reproduced.

Session inspection confirmed opaque random browser tokens, SHA-256-derived hash-only persistence, HttpOnly cookies, `SameSite=Lax`, expiry and revocation enforcement, logout invalidation, password-change revocation, and rejection of forged, disabled-user, and deleting-user sessions. Raw session tokens were absent from database rows, frontend storage, and tested logs.

## Blue team

Login now consumes an atomic Redis Lua dual token bucket before Argon2 work. One bucket is keyed by the direct peer network and one by a hash of normalized account identity; raw email is not stored in limiter keys. Defaults are 10/minute with burst 5 per account and 30/minute with burst 10 per peer. A denied request returns `429` with `Retry-After`; unavailable Redis fails closed with a safe `503`.

Post-hardening tests prove distributed state, hashed account keys, bounded Argon2 work, deterministic reset isolation in tests, and unchanged uniform credential failures. Session behavior required no production change.
