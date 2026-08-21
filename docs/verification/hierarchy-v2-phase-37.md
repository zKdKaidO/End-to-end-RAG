# Hierarchy V2 Phase 37 — Non-destructive Restart

Status: **PASS**

Restarted `postgres`, `api`, and `frontend` using `docker compose restart`; no volume was deleted.

- API health recovered.
- Persistent documents remained present.
- The three evaluation documents retained 965/965 `block3-v1` indexes.
- PostgreSQL public table count remained 10.
- Real hierarchy-recoverable retrieval returned 13 candidates (10 base + 3 children).
- Real DebugTrace reported `EXPANDED`, three hierarchy candidates, 13 final candidates, legal-rag-v2, and completed generation.
- The provider reconnected successfully through the real generation path.

