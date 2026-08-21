# Block 4 Phase 12 — Full regression

Status: PASS

Final command:

```text
docker compose exec -T api python -m pytest tests -v
```

Exact result:

```text
collected: 82
passed: 82
failed: 0
skipped: 0
warnings: 6
duration: 83.56s
```

The 43-test untouched Block 1–3 baseline passed before implementation, and all those tests remained green in the final combined suite.

Restart verification also passed: API and PostgreSQL were restarted with `docker compose restart postgres api`; no volumes were removed, cache files remained, pgvector remained 0.5.1, indexes remained present, and retrieval returned the expected first-ranked canonical chunk.
