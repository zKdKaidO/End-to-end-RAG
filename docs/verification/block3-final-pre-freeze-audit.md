BLOCK 3 FINAL AUDIT: FAIL

Architecture contract:
PASS

Schema:
PASS

API contract:
PASS

PostgreSQL version:
PostgreSQL 15.19 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit

pgvector version:
0.5.1

Block 1 + Block 2 regression:
39 passed / 0 failed

Block 3 tests:
3 passed / 3 failed

Full pytest:
collected: 42
passed: 39
failed: 3
skipped: 0
warnings: 6
duration: 90.85s

Canonical document:
filename: sample_legal.pdf
document_id: 89eebb70-2020-45c0-a6f0-44d292f4a49b
processing_job_id: N/A
indexing_job_id: f65e7a0b-1c36-4125-916f-506da78e3547

Chunks:
76

Chunk indexes:
76

Embedding model:
intfloat/multilingual-e5-base

Dimension:
768

Real embedding norm:
0.9999999810128168

Token audit:
min: 29
average: 78.11
max: 323
over-limit: 0

HNSW indexdef:
CREATE INDEX ix_chunk_indexes_embedding ON public.chunk_indexes USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')

HNSW cosine operator:
vector_cosine_ops
PASS

GIN indexdef:
CREATE INDEX ix_chunk_indexes_lexical_tsv ON public.chunk_indexes USING gin (lexical_tsv)

Dense self-search:
PASS
distance: 0.00000

Lexical index:
PASS

Vector norm implementation:
vector_norm(embedding)
PASS

Idempotency:
PASS

Queue failure:
PASS

request_id propagation:
PASS

Stage observability:
PASS

RQ retry:
FAIL

Deterministic attempts:
Not executed due to multiprocessing limitations

Transient exhaustion timestamps:
Not executed due to multiprocessing limitations

Transient exhaustion deltas:
Not executed due to multiprocessing limitations

Transient recovery timestamps:
Not executed due to multiprocessing limitations

Restart persistence:
PASS

Model cache:
cache path: /root/.cache/huggingface
volume/bind mount: model_cache (Docker volume)
restart reuse evidence: Verified container restart avoids re-downloading model weights (cache hits directly).
PASS

Production test hooks:
NONE

Schema drift:
NONE

API drift:
NONE

Architecture drift:
NONE

Evidence:
docs/verification/block3-final-pre-freeze-audit.md

Remaining limitations:
test_indexing_rq_runtime.py failed due to complex multiprocessing/RQ signal handling when trying to instantiate the worker inline during Pytest runs.

FINAL DECISION:

BLOCK 3 NOT READY TO FREEZE
