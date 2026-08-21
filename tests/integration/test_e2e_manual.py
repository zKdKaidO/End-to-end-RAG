import httpx as requests
import time
import sys
import os

API_URL = "http://localhost:8000"

def run_e2e():
    print("=== E2E TEST START ===")
    
    # 1. Upload
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_legal.pdf")
    with open(fixture_path, "rb") as f:
        files = {"file": ("sample_legal.pdf", f, "application/pdf")}
        print("Uploading...")
        resp = requests.post(f"{API_URL}/documents", files=files)
        
    assert resp.status_code == 202, f"Expected 202, got {resp.status_code}"
    doc_data = resp.json()["document"]
    doc_id = doc_data["id"]
    print(f"Uploaded! Document ID: {doc_id}")
    
    # 2. Poll for COMPLETED
    print("Polling status...")
    max_retries = 15
    for i in range(max_retries):
        resp = requests.get(f"{API_URL}/documents/{doc_id}")
        assert resp.status_code == 200
        current_status = resp.json()["status"]
        print(f"[{i}] Status: {current_status}")
        if current_status == "COMPLETED":
            break
        elif current_status == "FAILED":
            print("Job failed!")
            sys.exit(1)
        time.sleep(1)
        
    assert current_status == "COMPLETED", "Did not complete in time"
    
    # 3. Verify Pages
    print("Fetching pages...")
    resp = requests.get(f"{API_URL}/documents/{doc_id}/pages?limit=10")
    pages = resp.json()["data"]
    print(f"Found {len(pages)} pages.")
    assert len(pages) == 8, f"Expected 8 pages, got {len(pages)}"
    
    print("First page preview:")
    print(pages[0]["raw_text_snippet"])
    
    # 4. Deduplication
    print("Testing Deduplication...")
    with open(fixture_path, "rb") as f:
        files = {"file": ("sample_legal.pdf", f, "application/pdf")}
        resp = requests.post(f"{API_URL}/documents", files=files)
    
    dup_doc_id = resp.json()["document"]["id"]
    print(f"Deduplicated Document ID: {dup_doc_id}")
    assert dup_doc_id == doc_id, "Deduplication failed!"
    
    print("=== E2E TEST SUCCESS ===")

if __name__ == "__main__":
    run_e2e()
