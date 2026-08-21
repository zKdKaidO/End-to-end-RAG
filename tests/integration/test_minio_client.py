import pytest
import uuid
from unittest.mock import patch
from app.storage.minio_client import MinioClient
from app.core.exceptions import ObjectStorageError

@pytest.fixture
def storage_client():
    return MinioClient()

@pytest.fixture
def cleanup_document_id(storage_client):
    """Fixture to ensure cleanup of uploaded objects during tests."""
    doc_id = str(uuid.uuid4())
    yield doc_id
    # Teardown: ensure it's deleted
    try:
        if storage_client.exists(doc_id):
            storage_client.delete(doc_id)
    except Exception:
        pass

def test_upload_download_delete_flow(storage_client, cleanup_document_id):
    document_id = cleanup_document_id
    test_data = b"Dummy PDF content"
    
    # 1. Upload
    uri = storage_client.upload_pdf(document_id, test_data)
    assert uri == f"minio://documents/{document_id}/original.pdf"
    
    # 2. Exists == True
    assert storage_client.exists(document_id) is True
    
    # 3. Download
    downloaded_data = storage_client.download_pdf(document_id)
    assert downloaded_data == test_data
    
    # 4. Delete
    storage_client.delete(document_id)
    
    # 5. Exists == False
    assert storage_client.exists(document_id) is False

def test_download_nonexistent(storage_client):
    document_id = str(uuid.uuid4())
    with pytest.raises(ObjectStorageError) as exc:
        storage_client.download_pdf(document_id)
    assert "not found" in str(exc.value)

def test_exists_nonexistent(storage_client):
    document_id = str(uuid.uuid4())
    assert storage_client.exists(document_id) is False

def test_healthcheck(storage_client):
    assert storage_client.check_health() is True

def test_minio_unavailable():
    # Force client to point to a non-existent endpoint
    with patch("app.core.config.settings.MINIO_ENDPOINT", "invalid-host:9999"):
        broken_client = MinioClient()
        document_id = str(uuid.uuid4())
        
        with pytest.raises(ObjectStorageError) as exc:
            broken_client.upload_pdf(document_id, b"data")
            
        assert "Failed to upload document" in str(exc.value)
        # Check chaining
        assert exc.value.__cause__ is not None
