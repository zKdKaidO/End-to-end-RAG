# Secrets, Logging, and Error Leakage V1

The audit reproduced a tracked local `.env` containing development database/MinIO credentials and a test helper containing a database password. Local credentials were rotated without recording their values, `.env` was removed from the Git index and ignored, compose fallbacks were removed, `.env.example` contains blanks, and the test helper now consumes configured `DATABASE_URL`.

`.dockerignore` excludes `.env` and `.env.*` while retaining `.env.example`. A clean rebuilt `rag-api` image reported `/app/.env` absent. Repository search and the rebuilt frontend bundle found no prior credential patterns or newly introduced secrets.

User-visible ingestion/indexing/debug failures now use a stable generic message while full exceptions remain in structured server logs. Malformed requests return bounded validation/security responses without SQL, Redis, MinIO, filesystem paths, stack traces, session tokens, or synthetic canaries. Request IDs are sanitized and capped before logging. Full embeddings, source documents, passwords and raw session cookies are not logged.

Git history may retain previously committed credentials; rotation is the authoritative mitigation. History rewrite is intentionally outside this local hardening change and should be coordinated before publishing historical objects.
