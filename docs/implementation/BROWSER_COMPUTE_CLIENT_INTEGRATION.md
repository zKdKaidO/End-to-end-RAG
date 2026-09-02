# Browser Compute Client Integration Reference

Use this only for the later human-owned frontend work. It is a protocol reference,
not bundled frontend code.

1. Call authenticated `GET /api/v1/compute/devices`; choose only a `READY`,
   protocol-compatible device with a valid endpoint generation, loopback port, and
   required capability.
2. Construct only `http://127.0.0.1:<port>`.
3. Create a fresh Web Crypto random browser nonce. Call authenticated
   `POST /api/v1/compute/devices/{device_id}/local-session-grants` with
   `{ "browser_nonce": "..." }` and the exact application Origin.
4. Call local `POST /v1/sessions` with `Origin`, `X-ZKD-Local-Grant`, and
   `X-ZKD-Browser-Nonce`. Keep `local_session_id` and `session_key` only in memory.
5. For every sensitive request, make the exact raw bytes first, calculate
   `HMAC-SHA256(secret, METHOD|PATH|TIMESTAMP|NONCE|SHA256(rawBytes))`, then send
   those same bytes with the frozen headers. Use a new nonce for every attempt.

6. Current production client methods also cover authenticated local `GET
   /v1/documents` and `DELETE /v1/documents/{document_id}`. Delete has an empty
   raw body, is signed through the same request envelope, and is never retried
   automatically after an ambiguous loopback failure. The list is local catalog
   metadata, not a substitute for the platform manifest read model.

Reference vectors: `tests/fixtures/browser_compute_hmac_v1.json`.
Reference algorithms: `tools/browser_protocol/browser_compute_reference.mjs` and
`tools/browser_protocol/reference_client.py`.

## Important boundaries

- Never persist or log the session secret; do not put it in a URL or send it to the
  platform.
- PDF bytes, extracted text, embeddings, retrieval evidence, context, and local
  answer content remain local. A user-selected cloud provider is the only defined
  direct external-generation path; ZKD is not a relay.
- Discard local session state on reload, endpoint-generation change, expiry,
  `SESSION_BINDING_INVALID`, `REVOKED`/`NOT_PAIRED`, or `UPDATE_REQUIRED`.
- A valid established local session may continue during platform outage. A missing
  or expired session cannot be renewed without the platform grant issuer.
- Do not blindly retry mutations after ambiguous network failure. Re-sign any
  permitted retry with a new timestamp and nonce.
- Do not use `no-cors`, CORS proxies, insecure browser flags, extensions, or custom
  non-loopback addresses. Chrome/Edge PNA validation remains outstanding.
