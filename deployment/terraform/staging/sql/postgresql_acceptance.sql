-- Run only against the newly provisioned staging database before canonical data migration.
-- This intentionally installs the required vector extension if the managed role permits it.
CREATE EXTENSION IF NOT EXISTS vector;

BEGIN;

CREATE TEMP TABLE zkd_staging_vector_acceptance (
    id uuid PRIMARY KEY,
    embedding vector(768) NOT NULL,
    lexical_tsv tsvector NOT NULL
);

CREATE INDEX zkd_staging_vector_acceptance_hnsw
    ON zkd_staging_vector_acceptance USING hnsw (embedding vector_cosine_ops);

CREATE INDEX zkd_staging_vector_acceptance_lexical_gin
    ON zkd_staging_vector_acceptance USING gin (lexical_tsv);

INSERT INTO zkd_staging_vector_acceptance (id, embedding, lexical_tsv)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    array_fill(0.0::real, ARRAY[768])::vector,
    to_tsvector('simple', 'doanh nghiệp bảo hiểm')
);

SELECT extversion AS pgvector_version FROM pg_extension WHERE extname = 'vector';
SELECT to_tsvector('simple', 'doanh nghiệp bảo hiểm') @@ websearch_to_tsquery('simple', 'doanh nghiệp') AS full_text_works;
SELECT 1 - (embedding <=> array_fill(0.0::real, ARRAY[768])::vector) AS cosine_score
FROM zkd_staging_vector_acceptance;

ROLLBACK;
