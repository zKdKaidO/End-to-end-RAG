# ZKD Cloudflare control plane

Production uses this Worker and D1 only for account, paired-device, presence,
metadata-only manifest, and browser-to-local grant control. PDFs, extracted
text, chunks, embeddings, retrieval context, prompts, and answers never enter
this service. Redis, MinIO/R2, PostgreSQL, Docker, and a Tunnel to a user PC
are not production dependencies.

The Worker preserves the existing control URLs under `/api/v1/compute`, the
Ed25519 device-request transcript, one-time replay protection, revocation
epochs, trusted-origin grants, and local grant consumption. It does **not**
proxy any local-compute request: the browser still calls the installed Compute
loopback service directly after receiving a short-lived signed grant.

## D1 data boundary and credentials

D1 contains only account/session records, device public keys and revocation
epochs, short-lived pairing challenges, presence, replay nonces, and the
metadata-only local-manifest read model. The schema comment is a hard review
guard: do not add content-bearing columns to it.

`users.password_hash` is deliberately a `pbkdf2-sha256` record with the form
`pbkdf2-sha256$iterations$base64-salt$base64-derived-key`. Existing PostgreSQL
Argon2 credentials cannot be copied into this field: a controlled account
migration must issue a password reset or provision new PBKDF2 records before
users can sign in. No user data migration occurs through this repository.

Before a remote deployment, set exactly this Worker secret:

```powershell
npx wrangler secret put GRANT_SIGNING_PRIVATE_KEY_B64
```

Its value is the existing raw 32-byte Ed25519 private key, standard-base64
encoded. Its public key must remain the local Compute verifier's configured
grant public key; do not generate a mismatched key during rollout. Opaque
session tokens are random, stored only as SHA-256 hashes in D1, and sent in a
secure, HttpOnly, SameSite=Lax cookie.

## Local validation

```powershell
cd cloud
npx wrangler d1 migrations apply zkd-control-plane --local
npx wrangler deploy --dry-run --env=""
```

## First cloud deployment (interactive authorization required)

```powershell
npx wrangler login
npx wrangler d1 create zkd-control-plane-staging
# Copy the returned staging ID and workers.dev/custom staging origin into
# wrangler.jsonc. Staging and production must not share a D1 database.
npx wrangler d1 migrations apply zkd-control-plane-staging --remote --env staging
npx wrangler secret put GRANT_SIGNING_PRIVATE_KEY_B64 --env staging
npx wrangler deploy --env staging

# Only after the staging smoke is accepted:
npx wrangler d1 create zkd-control-plane
# copy the returned database_id into wrangler.jsonc; do not invent one
npx wrangler d1 migrations apply zkd-control-plane --remote
npx wrangler secret put GRANT_SIGNING_PRIVATE_KEY_B64
npx wrangler deploy
```

Verify the workers.dev staging URL, create a staging-only account and pair a
staging-only Compute device before binding `rag.zkd.id.vn`. Only then configure
the production route/custom domain and retire the existing tunnel. Never point
the existing production Compute installation at staging, and never reuse a D1
database or signing key across those environments.
