import pytest
import time
import uuid
from unittest.mock import patch
from redis import Redis
from rq import Queue, Retry, SimpleWorker
from rq.job import Job

from app.models.indexing_job import IndexingJob
from app.db.database import SessionLocal
from app.repositories.indexing_job_repo import IndexingJobRepository
from app.models.document import Document

pytestmark = pytest.mark.isolated_document_corpus
from app.indexing_worker_main import process_indexing
from app.indexing.constants import CANONICAL_INDEX_VERSION
from sqlalchemy.exc import OperationalError

@pytest.fixture
def queue_name():
    return f"document-indexing-test-{uuid.uuid4()}"

@pytest.fixture
def raw_redis():
    return Redis(host='redis', port=6379)

def setup_fake_doc(db_session):
    doc_id = str(uuid.uuid4())
    doc = Document(id=doc_id, filename='fake.pdf', mime_type='application/pdf', file_size=123, status='COMPLETED', sha256=doc_id)
    db_session.add(doc)
    db_session.commit()
    from app.models.chunk import Chunk
    chunk = Chunk(id=str(uuid.uuid4()), document_id=doc_id, legal_unit_id=None, chunk_index=0, content_text='Test content', embedding_text='Test content', page_start=1, page_end=1, metadata_json={}, provenance_json={})
    db_session.add(chunk)
    db_session.commit()
    return doc_id

def test_deterministic_failure_classification(raw_redis, queue_name):
    # Test A: Deterministic Classification
    db_session = SessionLocal()
    doc_id = setup_fake_doc(db_session)
    repo = IndexingJobRepository(db_session)
    db_job = repo.create_job(doc_id, CANONICAL_INDEX_VERSION, "test-model")
    job_id = str(db_job.id)

    q = Queue(queue_name, connection=raw_redis)
    job = q.enqueue(
        process_indexing,
        kwargs={'indexing_job_id': job_id, 'document_id': doc_id, 'request_id': 'test'},
        job_id=job_id,
        retry=Retry(max=2, interval=[2, 5])
    )

    def mock_encode_batch(self, batch):
        raise ValueError("Deterministic fault injection")

    with patch('app.indexing.embedder.E5Embedder.encode_batch', mock_encode_batch):
        worker = SimpleWorker([queue_name], connection=raw_redis)
        worker.work(burst=True)

    db_session.expunge_all()
    db_job = repo.get_by_id(job_id)
    
    assert db_job.status == "FAILED"
    assert db_job.error_stage == "EMBEDDING"
    
    # SimpleWorker processes job fully. Verify the job's retry mechanism is aborted.
    updated_job = Job.fetch(job_id, connection=raw_redis)
    assert updated_job.retries_left == 0
    assert updated_job.get_status() == "failed"

def test_transient_failure_classification(raw_redis, queue_name):
    # Test A: Transient Classification
    db_session = SessionLocal()
    doc_id = setup_fake_doc(db_session)
    repo = IndexingJobRepository(db_session)
    db_job = repo.create_job(doc_id, CANONICAL_INDEX_VERSION, "test-model")
    job_id = str(db_job.id)

    q = Queue(queue_name, connection=raw_redis)
    job = q.enqueue(
        process_indexing,
        kwargs={'indexing_job_id': job_id, 'document_id': doc_id, 'request_id': 'test'},
        job_id=job_id,
        retry=Retry(max=2, interval=[2, 5])
    )

    def mock_encode_batch(self, batch):
        raise OperationalError("Transient fault injection", None, None)

    with patch('app.indexing.embedder.E5Embedder.encode_batch', mock_encode_batch):
        worker = SimpleWorker([queue_name], connection=raw_redis)
        worker.work(burst=True)

    # In SimpleWorker with a burst, if it fails and has retries, the job gets requeued to the scheduled registry!
    updated_job = Job.fetch(job_id, connection=raw_redis)
    assert updated_job.retries_left == 1
    assert updated_job.get_status() == "scheduled"


