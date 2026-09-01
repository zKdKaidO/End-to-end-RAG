# ZKD Compute MVP — Phase C.2

Local retrieval is synchronous over `INDEX_READY` artifact SQLite databases.
`LocalRetrievalStore` wraps canonical `QueryEmbedder` for locked, normalized
768-D `query: ` E5 embeddings; uses exact NumPy dot-product cosine over validated
float32 BLOBs; uses FTS5 with a safe normalized-token OR query; and applies the
frozen 50/50/60/10 RRF contract with deterministic ID ties. Results hydrate
chunk content, legal-unit ID, metadata, provenance, branch scores/ranks, and
final rank. Document IDs must be locally index-ready; no manifest-only source
is queried. The authenticated local endpoint is `POST /v1/queries`.

No LLM, cloud, PostgreSQL, Redis/RQ, MinIO, or frontend dependency exists.
Hierarchy expansion and Block 5 integration remain explicit follow-up work;
the stored legal-unit IDs and provenance support that next step. Browser
acceptance remains unavailable.
