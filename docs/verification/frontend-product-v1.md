# Frontend Product V1 Verification

## Audit result

The existing React/Vite SPA, four routes, typed API client, SSE parser, Docker/nginx frontend, debug gate, and frozen backend contracts were retained. No backend defect was found and no backend file was modified for this productization work.

Main pre-change gaps were a fixed 1120 px minimum page width, dark-only decorative background, generic tables, per-delta React answer commits, no resizable source workspace, duplicated drawer/header primitives, and limited route-state coverage.

## Implemented verification surface

- Responsive compact workstation shell with light/dark tokens and dev-tool gating.
- Searchable document library, upload lifecycle feedback, compact corpus summary, and accessible lineage drawer.
- Buffered SSE research session, resizable/collapsible source pane, mobile source drawer, exact mapped citation interaction, cancellation, and development render counters.
- Inspectable pipeline rail with progressive candidate/context/generation detail.
- Searchable evaluation cases and accessible expected/measured case inspector.
- Visible focus states, dialog focus containment/restoration, Escape close, reduced-motion rules, and bounded horizontal table scrolling.

## Automated verification

Command: `npm test`

- Test files: 7
- Tests: 20
- Failed: 0
- Coverage areas: routes, document states/detail, SSE start/done/error/buffering/cancel, citations, source collapse/restore, debug disabled and pipeline trace, evaluation dataset/case inspection.

Command: `npm run build`

- TypeScript build: PASS
- Vite production build: PASS
- Modules transformed: 1820
- Main JS: approximately 309 kB / 97 kB gzip
- Main CSS: approximately 19 kB / 4.8 kB gzip

## Browser and backend verification

Docker frontend image rebuild and no-dependency container recreation: PASS at `http://localhost:5173`.

Automated browser QA used the production nginx build at 1440 × 1000 and 390 × 844:

- Documents loaded 1,193 development records, rendered the bounded first 100, searched the full set, and opened/closed an exact lineage drawer.
- Ask completed a real Vietnamese legal query, streamed a production answer, mapped three citations, focused `[S1]`, and exercised Sources collapse/restore.
- Debug completed one real evaluation-linked trace and exposed retrieval, context, generation, and expected/actual stages.
- Evaluation loaded its frozen summary/cases and opened the expected/measured inspector.
- Browser console errors: none.
- WCAG 2 A/AA automated audit on the narrow Ask route: 19 passed checks, 0 incomplete, 0 violations after remediation.

Preferred backend regression command: `docker compose exec -e PYTHONPATH=/app api python -m pytest tests -v`.

- Collected: 245
- Passed: 245
- Failed: 0
- Warnings: 8 existing deprecation/test warnings
- Duration: 91.81 seconds

## Architecture evidence

- Backend RAG semantics: unchanged.
- Blocks 1–6: unchanged by this task.
- Database schema: unchanged.
- Answer/SSE wire contract: unchanged.
- Production model and prompt: unchanged.
- New production database or queue infrastructure: none.

## Known limitations

- Document list/detail reads are intentionally backed by internal observability APIs; in a production-like environment with debug disabled, upload still uses the public ingestion endpoint but corpus inspection is unavailable under the current backend contract.
- Full source text inspection likewise requires the internal chunk endpoint; mapped citation metadata remains visible when it is disabled.
- Evaluation V2 metadata fields are limited to what current machine-readable reports expose.
