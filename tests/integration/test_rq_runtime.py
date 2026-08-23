import time
import uuid
import pytest
import threading
from unittest.mock import patch
from redis import Redis
from rq import Queue, Worker, Retry
from rq.job import Job
from rq.registry import FailedJobRegistry, ScheduledJobRegistry
from sqlalchemy.exc import OperationalError

from app.db.database import SessionLocal
from app.repositories.processing_job_repo import ProcessingJobRepository
from app.models.document import Document
from sqlalchemy import text

@pytest.fixture
def redis_client():
    return Redis(host="redis", port=6379, decode_responses=True)

@pytest.fixture
def raw_redis():
    return Redis(host="redis", port=6379)

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def setup_fake_doc(db):
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, filename='fake.pdf', mime_type='application/pdf', file_size=123, status='COMPLETED', sha256=str(doc_id))
    db.add(doc)
    db.commit()
    return str(doc_id)

class WorkerThread(threading.Thread):
    def __init__(self, raw_redis, queue_name):
        super().__init__(daemon=True)
        self.raw_redis = raw_redis
        from rq import Worker
        self.worker = Worker([queue_name], connection=raw_redis)

    def run(self):
        import signal
        with patch('signal.signal'):
            try:
                self.worker.work(with_scheduler=True)
            except Exception as e:
                print(f"Worker thread crashed: {e}")

    def stop(self):
        self.worker._stop_requested = True
        if self.worker.scheduler is not None:
            self.worker.stop_scheduler()
        self.join(timeout=2)

@pytest.fixture
def queue_name():
    return f"document-processing-test-{uuid.uuid4()}"

@pytest.fixture(scope="function")
def test_worker(queue_name):
    raw_redis = Redis(host="redis", port=6379)
    raw_redis.flushdb()
    thread = WorkerThread(raw_redis, queue_name)
    thread.start()
    yield thread
    thread.stop()

def enqueue_test_job(raw_redis, job_id, doc_id, queue_name):
    from rq import Queue, Retry
    q = Queue(queue_name, connection=raw_redis)
    from app.processing_worker_main import process_document
    q.enqueue(
        process_document,
        kwargs={'document_id': doc_id, 'processing_job_id': job_id, 'request_id': 'test'},
        job_id=job_id,
        retry=Retry(max=2, interval=[2, 5])
    )

def test_deterministic_failure_no_retry(redis_client, raw_redis, db_session, test_worker, queue_name):
    doc_id = setup_fake_doc(db_session)
    repo = ProcessingJobRepository(db_session)
    db_job = repo.create_job(doc_id)
    job_id = str(db_job.id)
    
    redis_client.delete(f"test_exec_timestamps:{job_id}")
    
    def mock_parse(*args, **kwargs):
        from redis import Redis
        r = Redis(host="redis", port=6379, decode_responses=True)
        r.rpush(f"test_exec_timestamps:{job_id}", str(time.time()))
        raise ValueError("Deterministic fault injection")

    with patch('app.processing.parser.LegalParser.parse', side_effect=mock_parse):
        enqueue_test_job(raw_redis, job_id, doc_id, queue_name)
        
        # Wait for execution and failure
        time.sleep(6)
        
    db_session.expunge_all()
    db_job = repo.get_by_id(job_id)
    assert db_job.status == "FAILED"
    
    timestamps = redis_client.lrange(f"test_exec_timestamps:{job_id}", 0, -1)
    assert len(timestamps) == 1, f"Expected 1 execution, got {len(timestamps)}: {timestamps}"
    
    job = Job.fetch(job_id, connection=raw_redis)
    assert job.get_status() == "failed"
    assert job.retries_left == 0
    

def test_transient_retry_exhaustion(redis_client, raw_redis, db_session, test_worker, queue_name):
    doc_id = setup_fake_doc(db_session)
    repo = ProcessingJobRepository(db_session)
    db_job = repo.create_job(doc_id)
    job_id = str(db_job.id)
    
    redis_client.delete(f"test_exec_timestamps:{job_id}")
    
    def mock_parse(*args, **kwargs):
        from redis import Redis
        r = Redis(host="redis", port=6379, decode_responses=True)
        r.rpush(f"test_exec_timestamps:{job_id}", str(time.time()))
        from sqlalchemy.exc import OperationalError
        raise OperationalError("Transient fault injection", None, None)

    with patch('app.processing.parser.LegalParser.parse', side_effect=mock_parse):
        enqueue_test_job(raw_redis, job_id, doc_id, queue_name)
        from rq.scheduler import RQScheduler
        from rq import Queue
        q = Queue(queue_name, connection=raw_redis)
        for _ in range(6):
            time.sleep(2)
            RQScheduler(queues=[q], connection=raw_redis).enqueue_scheduled_jobs()
        
    db_session.expunge_all()
    db_job = repo.get_by_id(job_id)
    assert db_job.status == "FAILED"
    
    timestamps = redis_client.lrange(f"test_exec_timestamps:{job_id}", 0, -1)
    assert len(timestamps) == 3, f"Expected 3 executions, got {len(timestamps)}: {timestamps}"
    
    job = Job.fetch(job_id, connection=raw_redis)
    assert job.get_status() == "failed"
    assert job.retries_left == 0


def test_transient_recovery(redis_client, raw_redis, db_session, test_worker, queue_name):
    doc_id = setup_fake_doc(db_session)
    repo = ProcessingJobRepository(db_session)
    db_job = repo.create_job(doc_id)
    job_id = str(db_job.id)
    
    redis_client.delete(f"test_exec_timestamps:{job_id}")
    
    def mock_parse(*args, **kwargs):
        from redis import Redis
        r = Redis(host="redis", port=6379, decode_responses=True)
        r.rpush(f"test_exec_timestamps:{job_id}", str(time.time()))
        count = r.llen(f"test_exec_timestamps:{job_id}")
        if count == 1:
            from sqlalchemy.exc import OperationalError
            raise OperationalError("Transient fault injection (attempt 1)", None, None)
        return []

    with patch('app.processing.parser.LegalParser.parse', side_effect=mock_parse):
        enqueue_test_job(raw_redis, job_id, doc_id, queue_name)
        from rq.scheduler import RQScheduler
        from rq import Queue
        q = Queue(queue_name, connection=raw_redis)
        for _ in range(4):
            time.sleep(2)
            RQScheduler(queues=[q], connection=raw_redis).enqueue_scheduled_jobs()
        
    db_session.expunge_all()
    timestamps = redis_client.lrange(f"test_exec_timestamps:{job_id}", 0, -1)
    assert len(timestamps) == 2, f"Expected 2 executions, got {len(timestamps)}: {timestamps}"
    
    job = Job.fetch(job_id, connection=raw_redis)
    assert job.get_status() == "finished"
