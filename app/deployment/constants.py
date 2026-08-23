BACKUP_FORMAT_VERSION = 1
TOMBSTONE_FORMAT_VERSION = 1
HNSW_INDEX_NAME = "ix_chunk_indexes_embedding"
HNSW_CREATE_SQL = """
CREATE INDEX ix_chunk_indexes_embedding
ON public.chunk_indexes
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64)
""".strip()

# Stable signed bigint used only for PostgreSQL advisory locking. Mutations
# take a shared lock; backup takes the exclusive form of the same key.
BACKUP_BARRIER_KEY = 0x5241474241434B55
