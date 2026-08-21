import uuid, time, json, urllib.request
from app.db.database import SessionLocal
from app.repositories.indexing_job_repo import IndexingJobRepository

db = SessionLocal()
from sqlalchemy import text
res = db.execute(text("SELECT document_id FROM chunks GROUP BY document_id HAVING count(*) > 0 LIMIT 1")).fetchone()
if not res:
    print('No documents found')
    exit(1)
doc_id = str(res[0])
print(f'Using doc_id: {doc_id}')

req = urllib.request.Request(f'http://localhost:8000/documents/{doc_id}/index', data=json.dumps({}).encode(), headers={'Content-Type': 'application/json'})
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print('Enqueued:', data)
    job_id = data['job_id']
except Exception as e:
    print('Failed to enqueue:', e)
    if hasattr(e, 'read'): print(e.read())
    exit(1)

for _ in range(60):
    resp = urllib.request.urlopen(f'http://localhost:8000/indexing-jobs/{job_id}')
    data = json.loads(resp.read())
    status = data['status']
    print('Status:', status)
    if status in ('COMPLETED', 'FAILED'):
        break
    time.sleep(2)

print('Final Status:', data)
res = db.execute(text('SELECT count(*) FROM chunk_indexes WHERE document_id = :did'), {'did': doc_id}).fetchone()
print(f'Chunks indexed: {res[0]}')
