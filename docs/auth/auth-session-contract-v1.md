# Auth Session Contract V1

Passwords are hashed by `argon2-cffi` using Argon2id. Passphrases are accepted from 12 through 1024 characters; no reversible or plaintext password is stored.

Login creates 32 random bytes encoded as an opaque token. Only `SHA-256(raw_token)` is stored in `auth_sessions`. Resolution requires an unrevoked, unexpired session and an `ACTIVE` user. The fixed default TTL is 24 hours and is not sliding.

The browser cookie contract is:

- name: `legal_rag_session`
- `HttpOnly`
- `SameSite=Lax`
- `Path=/`
- `Secure=true` in production

Local HTTP development explicitly configures `AUTH_COOKIE_SECURE=false`; production deployments must set it to true and place frontend/API behind the same-origin reverse proxy.

Credentialed CORS uses exact configured origins and never `*`. Unsafe cookie-authenticated requests require a trusted `Origin`. Logout, password change, user disable, and account-deletion request revoke server sessions. The frontend uses `credentials: include` and never reads or stores the token in local/session storage.

Unknown email and invalid password use the same `401 INVALID_CREDENTIALS` response and an Argon2 dummy verification path. Missing, forged, expired, revoked, disabled-user, and deleting-user sessions all resolve to `401 AUTHENTICATION_REQUIRED`.
