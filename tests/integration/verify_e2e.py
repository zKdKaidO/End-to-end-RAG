import httpx
import time
import sys
import os
import psycopg2
import hashlib

API_URL = "http://localhost:8000"
FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_legal.pdf")

def run():
    print("\n=== 2. Canonical E2E Ingestion ===")
    with open(FIXTURE, "rb") as f:
        files = {"file": ("sample_legal.pdf", f, "application/pdf")}
        resp = httpx.post(f"{API_URL}/documents", files=files)
        
    print(f"HTTP status: {resp.status_code}")
    body = resp.json()
    print(f"Response body: {body}")
    
    doc_id = body["document"]["id"]
    print(f"document_id: {doc_id}")
    
    conn = psycopg2.connect("dbname=rag_db user=postgres password=postgres host=postgres")
    cur = conn.cursor()
    cur.execute("SELECT id FROM ingestion_jobs WHERE document_id = %s;", (doc_id,))
    job_id = cur.fetchone()[0]
    print(f"job_id: {job_id}")
    
    print("Polling status...")
    last_status = None
    last_stage = None
    for _ in range(30):
        r = httpx.get(f"{API_URL}/ingestion-jobs/{job_id}")
        j = r.json()
        if j["status"] != last_status or j["current_stage"] != last_stage:
            print(f"Transition: {last_status or 'PENDING'} -> {j['status']} (Stage: {j['current_stage']})")
            last_status = j["status"]
            last_stage = j["current_stage"]
        if last_status in ["COMPLETED", "FAILED"]:
            break
        time.sleep(0.5)

    print("\n=== 3. Verify PostgreSQL directly ===")
    cur.execute("SELECT id, filename, sha256, storage_uri, page_count, status FROM documents WHERE id = %s;", (doc_id,))
    doc_row = cur.fetchone()
    print(f"documents: {doc_row}")
    
    cur.execute("SELECT id, document_id, status, current_stage, pages_total, pages_processed, error_stage, error_type, error_message FROM ingestion_jobs WHERE id = %s;", (job_id,))
    job_row = cur.fetchone()
    print(f"ingestion_jobs: {job_row}")
    
    cur.execute("SELECT COUNT(*) FROM document_pages WHERE document_id = %s;", (doc_id,))
    page_count = cur.fetchone()[0]
    print(f"document_pages count = {page_count}")
    
    cur.execute("SELECT page_number, substring(raw_text, 1, 50) FROM document_pages WHERE document_id = %s ORDER BY page_number ASC;", (doc_id,))
    pages = cur.fetchall()
    print("Page 1 preview:", pages[0])
    print("Page 4 preview:", pages[3])
    print("Page 8 preview:", pages[7])

    print("\n=== 4. Prove page persistence idempotency explicitly ===")
    print("Executing batch_upsert_pages with the same data again...")
    # Rerun the job process directly in Python or using API
    # Since the api doesn't expose it, we can trigger worker task
    from rq import Queue
    from redis import Redis
    from app.worker_main import process_ingestion
    
    # Just run it directly
    process_ingestion(job_id, doc_id)
    
    cur.execute("SELECT COUNT(*) FROM document_pages WHERE document_id = %s;", (doc_id,))
    new_page_count = cur.fetchone()[0]
    print(f"After idempotent re-run, document_pages count = {new_page_count}")
    
    print("\n=== 7. Prove MinIO state ===")
    from app.storage.minio_client import minio_client
    dl_bytes = minio_client.download_pdf(doc_id)
    dl_hash = hashlib.sha256(dl_bytes).hexdigest()
    
    with open(FIXTURE, "rb") as f:
        orig_bytes = f.read()
    orig_hash = hashlib.sha256(orig_bytes).hexdigest()
    
    print(f"downloaded object SHA-256: {dl_hash}")
    print(f"sample_legal.pdf SHA-256:  {orig_hash}")
    print(f"documents.sha256:          {doc_row[2]}")
    assert dl_hash == orig_hash == doc_row[2], "Hashes do not match!"

    print("\n=== 8. Prove deduplication after COMPLETED ===")
    with open(FIXTURE, "rb") as f:
        files = {"file": ("sample_legal.pdf", f, "application/pdf")}
        resp2 = httpx.post(f"{API_URL}/documents", files=files)
        
    doc2_id = resp2.json()["document"]["id"]
    print(f"Second upload document_id: {doc2_id}")
    assert doc2_id == doc_id, "Deduplication failed!"
    
    cur.execute("SELECT COUNT(*) FROM documents")
    print(f"Total documents: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM ingestion_jobs")
    print(f"Total ingestion_jobs: {cur.fetchone()[0]}")
    
    conn.close()

if __name__ == "__main__":
    run()
