import uuid, time, json, urllib.request, math
from app.db.database import SessionLocal
from app.repositories.indexing_job_repo import IndexingJobRepository
from sqlalchemy import text
from sentence_transformers import SentenceTransformer

db = SessionLocal()

doc_id = db.execute(text("SELECT id FROM documents WHERE filename = 'sample_legal.pdf' AND status = 'COMPLETED' LIMIT 1")).scalar()
if not doc_id:
    print('No completed sample_legal.pdf found')
    exit(1)
doc_id = str(doc_id)

processing_job = None
proc_job_id = str(processing_job) if processing_job else 'None'

page_count = db.execute(text("SELECT count(*) FROM document_pages WHERE document_id = :did"), {'did': doc_id}).scalar()
chunks_count = db.execute(text("SELECT count(*) FROM chunks WHERE document_id = :did"), {'did': doc_id}).scalar()

print(f'Canonical document:\nfilename: sample_legal.pdf\ndocument_id: {doc_id}\nprocessing_job_id: {proc_job_id}\n')
print(f'page_count: {page_count}\nchunks count: {chunks_count}')

req = urllib.request.Request(f'http://localhost:8000/documents/{doc_id}/index', data=json.dumps({}).encode(), headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
job_id = data['job_id']
print(f'indexing_job_id: {job_id}')

for _ in range(60):
    resp = urllib.request.urlopen(f'http://localhost:8000/indexing-jobs/{job_id}')
    data = json.loads(resp.read())
    status = data['status']
    if status in ('COMPLETED', 'FAILED'): break
    time.sleep(2)

print(f'Status: {status}')

chunk_indexes_count = db.execute(text("SELECT count(*) FROM chunk_indexes WHERE document_id = :did"), {'did': doc_id}).scalar()
print(f'chunk_indexes count: {chunk_indexes_count}')

index_row = db.execute(text("""
    SELECT embedding_dimension, embedding_model, index_version, vector_norm(embedding), lexical_tsv
    FROM chunk_indexes WHERE document_id = :did LIMIT 1
"""), {'did': doc_id}).fetchone()

print(f'Embedding model: {index_row[1]}')
print(f'Dimension: {index_row[0]}')
print(f'Real embedding norm: {index_row[3]}')
print(f'Index version: {index_row[2]}')
print(f'Lexical TSV present: {index_row[4] is not None}')

# REINDEX
req = urllib.request.Request(f'http://localhost:8000/documents/{doc_id}/index', data=json.dumps({}).encode(), headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
job_id2 = data['job_id']

for _ in range(60):
    resp = urllib.request.urlopen(f'http://localhost:8000/indexing-jobs/{job_id2}')
    data = json.loads(resp.read())
    status = data['status']
    if status in ('COMPLETED', 'FAILED'): break
    time.sleep(2)

chunk_indexes_count2 = db.execute(text("SELECT count(*) FROM chunk_indexes WHERE document_id = :did"), {'did': doc_id}).scalar()
print(f'Idempotency PASS: {chunk_indexes_count == chunk_indexes_count2}')

# DENSE SELF SEARCH
row = db.execute(text("SELECT chunk_id, embedding FROM chunk_indexes WHERE document_id = :did LIMIT 1"), {'did': doc_id}).fetchone()
cid, emb = str(row[0]), row[1]
closest = db.execute(text("SELECT chunk_id, embedding <=> :emb as dist FROM chunk_indexes WHERE document_id = :did ORDER BY embedding <=> :emb LIMIT 1"), {'emb': emb, 'did': doc_id}).fetchone()
print(f'Dense self-search: PASS (chunk {closest[0]} distance {closest[1]:.5f})' if str(closest[0]) == cid and closest[1] < 0.001 else f'FAIL: {closest[0]} dist {closest[1]}')

# LEXICAL SEARCH
lex = db.execute(text("SELECT chunk_id FROM chunk_indexes WHERE document_id = :did AND lexical_tsv @@ to_tsquery('simple', 'lu?t') LIMIT 1"), {'did': doc_id}).fetchone()
print(f'Lexical index: PASS (found in chunk {lex[0]})' if lex else 'Lexical index: FAIL')

# TOKEN AUDIT
chunks = db.execute(text("SELECT embedding_text FROM chunks WHERE document_id = :did"), {"did": doc_id}).fetchall()
model = SentenceTransformer("intfloat/multilingual-e5-base", device='cpu')
max_tokens = model.max_seq_length

lengths = []
over_limit = 0
for r in chunks:
    passage = f"passage: {r[0]}"
    tokens = model.tokenizer.encode(passage)
    length = len(tokens)
    lengths.append(length)
    if length > max_tokens: over_limit += 1

print('Token audit:')
print(f'min: {min(lengths)}')
print(f'average: {sum(lengths)/len(lengths):.2f}')
print(f'max: {max(lengths)}')
print(f'over-limit: {over_limit}')
