import os
import time
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from redis import Redis
from rq import Queue

def verify_reprocess():
    doc_id = "93e29894-634f-4f70-b7e8-75e7cfff319f" # Use the one from step 5
    
    conn = psycopg2.connect(
        host="postgres",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="rag_db"
    )
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Reset processing job status to PENDING
    cursor.execute("UPDATE document_processing_jobs SET status = 'PENDING' WHERE document_id = %s", (doc_id,))
    
    # 2. Enqueue job
    print(f"Re-enqueuing processing for doc: {doc_id}")
    redis_conn = Redis(host="redis", port=6379)
    q = Queue('document-processing', connection=redis_conn)
    
    cursor.execute("SELECT id FROM document_processing_jobs WHERE document_id = %s", (doc_id,))
    p_job_id = cursor.fetchone()["id"]
    
    q.enqueue(
        'app.processing_worker_main.process_document',
        kwargs={'processing_job_id': str(p_job_id), 'document_id': str(doc_id), 'request_id': 'test-reprocess'},
        job_id=str(p_job_id),
        job_timeout='2h'
    )
    
    # 3. Wait for completion
    max_retries = 30
    for _ in range(max_retries):
        cursor.execute("SELECT status FROM document_processing_jobs WHERE id = %s", (p_job_id,))
        p_job = cursor.fetchone()
        
        print(f"Processing Job: {p_job['status']}")
        
        if p_job['status'] == 'COMPLETED':
            print("Reprocessing complete!")
            break
        if p_job['status'] == 'FAILED':
            raise RuntimeError("Processing Job Failed!")
            
        time.sleep(2)
    else:
        raise TimeoutError("Jobs did not complete in time")
        
    # 4. Verify no duplicates
    print("\n--- Verifying Reprocess Outputs ---")
    cursor.execute("SELECT count(*) as cnt FROM document_reconstructions WHERE document_id = %s", (doc_id,))
    print(f"Reconstructions count: {cursor.fetchone()['cnt']} (Expected: 1)")
    
    cursor.execute("SELECT count(*) as cnt FROM legal_units WHERE document_id = %s", (doc_id,))
    print(f"Legal Units count: {cursor.fetchone()['cnt']} (Expected: 76)")
    
    cursor.execute("SELECT count(*) as cnt FROM chunks WHERE document_id = %s", (doc_id,))
    print(f"Chunks count: {cursor.fetchone()['cnt']} (Expected: 76)")
    
    cursor.execute("SELECT id, legal_unit_id FROM chunks WHERE document_id = %s", (doc_id,))
    chunks = cursor.fetchall()
    
    # Check all legal_unit_ids resolve to existing legal units
    unit_ids_in_chunks = set([c['legal_unit_id'] for c in chunks if c['legal_unit_id']])
    if unit_ids_in_chunks:
        cursor.execute("SELECT id FROM legal_units WHERE document_id = %s", (doc_id,))
        valid_unit_ids = set([str(u['id']) for u in cursor.fetchall()])
        invalid_refs = [uid for uid in unit_ids_in_chunks if str(uid) not in valid_unit_ids]
        print(f"Invalid legal_unit_id references: {len(invalid_refs)}")
        assert len(invalid_refs) == 0
    else:
        print("No legal units referenced (Unexpected)")

if __name__ == "__main__":
    verify_reprocess()
