import os
import time
import httpx
import psycopg2
import json
from psycopg2.extras import RealDictCursor

def verify_block2_e2e():
    api_url = "http://api:8000/documents"
    pdf_path = "tests/fixtures/sample_legal.pdf"
    
    # 0. Clean DB first
    conn = psycopg2.connect(
        host="postgres",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="rag_db"
    )
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("TRUNCATE documents CASCADE")
    
    # 1. Upload
    print("Uploading sample_legal.pdf...")
    with open(pdf_path, 'rb') as f:
        files = {'file': ('sample_legal.pdf', f, 'application/pdf')}
        with httpx.Client() as client:
            resp = client.post(api_url, files=files)
        
    assert resp.status_code == 202, f"Expected 202, got {resp.status_code}. Response: {resp.text}"
    data = resp.json()
    
    if "job_id" in data:
        # Full response
        doc_id = data["job"]["document_id"]
    else:
        # Deduplicated response (should not happen after delete, but just in case)
        doc_id = data.get("document", {}).get("id")
        
    print(f"Document ID: {doc_id}")
    
    # 2. Wait for Processing to Complete
    print("Polling database for job completion...")
    
    conn = psycopg2.connect(
        host="postgres",
        port=5432,
        user="postgres",
        password="postgres",
        dbname="rag_db"
    )
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    max_retries = 30
    for _ in range(max_retries):
        cursor.execute("SELECT status FROM documents WHERE id = %s", (doc_id,))
        doc_status = cursor.fetchone()["status"]
        
        cursor.execute("SELECT status FROM document_processing_jobs WHERE document_id = %s", (doc_id,))
        p_job = cursor.fetchone()
        
        print(f"Doc Status: {doc_status} | Processing Job: {p_job['status'] if p_job else 'NOT_CREATED_YET'}")
        
        if p_job and p_job['status'] == 'COMPLETED':
            print("Processing complete!")
            break
        if p_job and p_job['status'] == 'FAILED':
            raise RuntimeError("Processing Job Failed!")
            
        time.sleep(2)
    else:
        raise TimeoutError("Jobs did not complete in time")
        
    # 3. Verify Database Records
    print("\n--- Verifying Block 2 Outputs ---")
    
    cursor.execute("SELECT id, length(normalized_text) as txt_len, jsonb_array_length(page_offset_map::jsonb) as pmap_len FROM document_reconstructions WHERE document_id = %s", (doc_id,))
    recon = cursor.fetchone()
    print(f"Reconstruction: Length = {recon['txt_len']} chars, Offset Map = {recon['pmap_len']} pages")
    
    cursor.execute("SELECT count(*) as cnt FROM legal_units WHERE document_id = %s", (doc_id,))
    unit_cnt = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT unit_type, count(*) as cnt FROM legal_units WHERE document_id = %s GROUP BY unit_type", (doc_id,))
    types = cursor.fetchall()
    
    print(f"Legal Units: {unit_cnt} total")
    for t in types:
        print(f" - {t['unit_type']}: {t['cnt']}")
        
    cursor.execute("SELECT count(*) as cnt FROM chunks WHERE document_id = %s", (doc_id,))
    chunk_cnt = cursor.fetchone()['cnt']
    print(f"Chunks: {chunk_cnt} total")
    
    cursor.execute("SELECT embedding_text, metadata_json, provenance_json FROM chunks WHERE document_id = %s LIMIT 1", (doc_id,))
    sample_chunk = cursor.fetchone()
    print("\nSample Chunk:")
    print("Metadata:", json.dumps(sample_chunk['metadata_json'], ensure_ascii=False))
    print("Provenance:", json.dumps(sample_chunk['provenance_json'], ensure_ascii=False))
    print("Embedding Text preview:", sample_chunk['embedding_text'][:100].replace('\n', ' '))
    
    conn.close()

if __name__ == "__main__":
    verify_block2_e2e()
