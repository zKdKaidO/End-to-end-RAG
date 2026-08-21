# Debug UI Phase 16 — Security and internal-route boundary

Date: 2026-08-19

- Internal routes require `DEBUG_UI_ENABLED` and a local/development/test environment.
- Disabled-route integration check: 404.
- Debug request schema forbids arbitrary model, temperature, Top-K, RRF, context-budget, system-prompt, and GenerationProfile overrides.
- Schemas expose public generation state and high-level prompt metadata only; no system prompt, private reasoning, provider internals, credentials, headers, or environment dump.
- CORS permits only configured development origins (default `http://localhost:5173`), GET/POST, and the needed headers; credentials and wildcard origins are disabled.
- Preflight from the allowed origin returned 200 with `Access-Control-Allow-Origin`; an untrusted origin returned 400 without that header.

Result: PASS.
