# Block 6 Phase 11 — SSE streaming

`POST /answer/stream` returns `text/event-stream`. Pre-generation validation finishes before the response opens; the provider/model health check also occurs before opening for evidence-bearing requests.

Unit/API and real Ollama runs verified `start → delta* → done`, multiple deltas, exact internal answer accumulation, citations validated only in authoritative `done`, no native NDJSON/timing/thinking objects, and no duplicate `done`. A failure after deltas produces `error` and never `done`.

Result: PASS.
