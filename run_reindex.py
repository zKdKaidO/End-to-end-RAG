import uuid, time, json, urllib.request
from app.db.database import SessionLocal
from app.repositories.indexing_job_repo import IndexingJobRepository

db = SessionLocal()
from sqlalchemy import text
doc_id = "1efc75bf-e911-4f1e-963f-14397dee69cb"

print(f'Reindexing doc_id: {doc_id}')

req = urllib.request.Request(f'http://localhost:8000/documents/{doc_id}/index', data=json.dumps({}).encode(), headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print('Enqueued 2nd time:', data)
job_id = data['job_id']

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
