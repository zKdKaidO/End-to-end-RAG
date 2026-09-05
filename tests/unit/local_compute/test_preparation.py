from __future__ import annotations
import hashlib
import sqlite3
import uuid
from pathlib import Path
import pymupdf
import pytest
from app.local_compute.documents import LocalDocumentStore
from app.core.config import settings as server_settings
from app.local_compute.errors import LocalComputeError
from app.local_compute.preparation import LocalPreparationService, ARTIFACT_PROFILE_ID
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.indexing import LocalIndexService
from app.local_compute.retrieval import LocalRetrievalStore
from app.local_compute.settings import LocalComputeSettings

def pdf_bytes(text: str) -> bytes:
    doc=pymupdf.open(); page=doc.new_page(); page.insert_text((72,72),text,fontsize=11); result=doc.tobytes(); doc.close(); return result

@pytest.fixture
def runtime(tmp_path):
    instance=LocalComputeRuntime(LocalComputeSettings(data_root=tmp_path/"Compute",development_mode=True,development_origins=("http://localhost:5173",),embedding_model_cache_dir=Path(server_settings.EMBEDDING_MODEL_CACHE_DIR)))
    instance.start(); yield instance; instance.shutdown()

def test_accept_prepare_promote_and_restart(runtime):
    source=pdf_bytes("NGHỊ ĐỊNH\nSố: 01/2026\nĐiều 1. Phạm vi điều chỉnh.\n1. Quy định này áp dụng cho doanh nghiệp.")
    doc_id=str(uuid.uuid4()); store=LocalDocumentStore(runtime.settings,runtime.catalog)
    accepted=store.accept_document(doc_id,[source[:10],source[10:]],"legal.pdf","application/pdf")
    assert accepted["content_sha256"]==hashlib.sha256(source).hexdigest()
    assert store.accept_document(doc_id,[source],"legal.pdf","application/pdf")["idempotent"]
    result=LocalPreparationService(runtime.settings,runtime.catalog).prepare(doc_id)
    assert result["preparation_state"]=="PREPARED_NOT_INDEXED" and result["chunk_count"]>0
    artifact=runtime.settings.artifacts_path/doc_id/result["artifact_id"]/"artifact.sqlite3"
    with sqlite3.connect(artifact) as db:
        assert db.execute("SELECT value FROM artifact_metadata WHERE key='profile_id'").fetchone()[0]==ARTIFACT_PROFILE_ID
        assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]>0
        assert db.execute("SELECT COUNT(*) FROM chunks WHERE token_count>512").fetchone()[0]==0
    reprocessed=LocalPreparationService(runtime.settings,runtime.catalog).prepare(doc_id)
    assert reprocessed["artifact_id"] != result["artifact_id"]
    assert artifact.exists()
    assert LocalDocumentStore(runtime.settings,runtime.catalog).get(doc_id)["active_artifact_id"] == reprocessed["artifact_id"]
    restarted=LocalComputeRuntime(runtime.settings); restarted.start()
    assert LocalDocumentStore(restarted.settings,restarted.catalog).get(doc_id)["active_artifact_id"]==reprocessed["artifact_id"]
    indexed=LocalIndexService(runtime.settings,runtime.catalog).index_document(doc_id)
    assert indexed["index_state"]=="INDEX_READY"
    with sqlite3.connect(runtime.settings.artifacts_path/doc_id/indexed["artifact_id"]/'artifact.sqlite3') as db:
        assert db.execute('SELECT COUNT(*) FROM chunk_embeddings').fetchone()[0]==indexed['embedding_count']
        assert db.execute('SELECT COUNT(*) FROM chunk_fts').fetchone()[0]==indexed['embedding_count']
        assert db.execute('SELECT length(vector) FROM chunk_embeddings LIMIT 1').fetchone()[0]==768*4
    results=LocalRetrievalStore(runtime.settings,runtime.catalog).query_document_set('doanh nghiệp áp dụng', [doc_id])
    assert results and results[0]['document_id']==doc_id and results[0]['provenance_json']['document_id']==doc_id

def test_rejects_invalid_conflicting_and_textless_sources(runtime):
    store=LocalDocumentStore(runtime.settings,runtime.catalog); doc_id=str(uuid.uuid4())
    with pytest.raises(LocalComputeError): store.accept_document(doc_id,[b"not-a-pdf"],"x.pdf","application/pdf")
    good=pdf_bytes("Điều 1. Nội dung hợp lệ."); store.accept_document(doc_id,[good],"x.pdf","application/pdf")
    with pytest.raises(LocalComputeError): store.accept_document(doc_id,[pdf_bytes("Điều 2. Khác.")],"x.pdf","application/pdf")
    empty=str(uuid.uuid4()); store.accept_document(empty,[pdf_bytes("")],"empty.pdf","application/pdf")
    with pytest.raises(LocalComputeError,match="Text-native"):
        LocalPreparationService(runtime.settings,runtime.catalog).prepare(empty)
