# Debug UI Phase 14 — Real backend/frontend integration

Date: 2026-08-19

Verified against real PostgreSQL, persisted corpus/indexes, frozen Blocks 4–6, Ollama, and qwen3.5:9b:

- Documents page loaded real stored records.
- Ask received a real streamed `COMPLETED` answer with citations.
- `[S1]` opened real stored evidence and provenance.
- Debug displayed 50 dense candidates, lexical contribution, final RRF Top 10, selected S1…S10, and generation output.
- A document-filtered trace returned only the requested document in dense, lexical, and final lists.
- A zero-evidence trace short-circuited to `INSUFFICIENT_EVIDENCE`.
- Evaluation artifacts loaded and `corporate_tax_rate_absent` reran through the real pipeline with diagnosis `PASS`.
- Browser console/page errors: none.

Screenshots: `docs/verification/debug-ui-browser.png`, `docs/verification/debug-ui-real-trace.png`, and `docs/verification/debug-ui-ask-real.png`.

Result: PASS.
