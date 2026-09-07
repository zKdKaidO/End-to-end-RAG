# Cloudflare control-plane staging and cutover gate

This is a staged replacement for the legacy cloud control plane only. It does
not move local documents or any RAG data to Cloudflare. The installed ZKD
Compute device continues to own the local catalog, source PDFs, extracted
text, chunks, embeddings, retrieval, context construction, citations, and
generation.

## Preconditions

1. Build the static frontend from the reviewed source. Its default relative
   `/api` base is required; do not configure a separate browser API origin.
2. Create separate staging and production D1 databases, and copy their IDs
   into the matching sections of `wrangler.jsonc`.
3. Configure a staging `PUBLIC_ORIGIN` that exactly matches the Worker static
   site origin. Configure the production value only when the production custom
   domain is ready.
4. Set `GRANT_SIGNING_PRIVATE_KEY_B64` separately in each environment. The
   matching public key must be provisioned into the corresponding local Compute
   verifier; production and staging must use distinct signing keys.
5. Provision a staging-only PBKDF2 account. Existing PostgreSQL Argon2 hashes
   are not format-compatible: migrate accounts through an approved password
   reset/provisioning flow, never by copying or weakening their hashes.

## Staging acceptance

Use the Workers staging URL and a staging-only installed Compute device:

1. Sign in, then check `/api/v1/auth/me` and logout.
2. Create a pairing challenge, complete pairing from the device, and confirm it
   in the browser. The raw pairing token and confirmation code must never be
   persisted by the device or returned after this flow.
3. Publish signed device presence and a metadata-only manifest. Inspect D1 to
   confirm that there is no content-bearing data.
4. Confirm that the browser receives a local session grant only from the exact
   trusted `PUBLIC_ORIGIN`; validate it at the local loopback service and prove
   its nonce cannot be consumed twice.
5. Revoke the device and confirm signed control calls and local grants fail.
6. Verify static routes load through the Worker and that the browser has no
   network request for a document, chunk, embedding, context, prompt, answer,
   Redis, MinIO, PostgreSQL, or a tunnel endpoint.

## Production cutover and rollback

Do not alter the existing Cloudflare Tunnel, DNS record, or production Compute
configuration until all staging checks pass. Bind the custom domain only after
the production Worker has its separate D1 database, matching grant verifier,
and a freshly provisioned production account/device.

If a production smoke fails before the old tunnel is retired, remove the new
route/custom-domain binding and keep the existing tunnel and platform URL
unchanged. If a fault is detected after binding but before the tunnel is
retired, restore the prior route to the existing tunnel and revoke any device
that was paired against the failed environment. Do not copy D1 state between
environments as a rollback shortcut.

## Explicitly deferred

- any migration of legacy documents, RAG history, evaluations, or vectors;
- centralized/platform-funded generation;
- Cloudflare access to local Compute over an inbound tunnel;
- user cloud-provider credentials or billing; and
- deletion of legacy Docker, PostgreSQL, Redis, MinIO, or tunnel resources.
