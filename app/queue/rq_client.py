from redis import Redis
from rq import Queue, Retry
from app.core.config import settings
from app.core.exceptions import QueueError
from app.core.logging import get_logger

logger = get_logger(__name__)

class RQClient:
    def __init__(self):
        self.redis_conn = Redis.from_url(settings.REDIS_URL)
        self.queue = Queue('ingestion', connection=self.redis_conn)
        self.processing_queue = Queue('document-processing', connection=self.redis_conn)
        self.indexing_queue = Queue('document-indexing', connection=self.redis_conn)
        self.account_deletion_queue = Queue('account-deletion', connection=self.redis_conn)
        self.document_gc_queue = Queue('document-gc', connection=self.redis_conn)

    def enqueue_ingestion_job(self, job_id: str, document_id: str, request_id: str = None):
        try:
            self.queue.enqueue(
                'app.worker_main.process_ingestion',
                kwargs={'job_id': job_id, 'document_id': document_id, 'request_id': request_id},
                job_id=job_id,
                job_timeout=settings.INGESTION_JOB_TIMEOUT_SECONDS,
                result_ttl=settings.RQ_RESULT_TTL_SECONDS,
                failure_ttl=settings.RQ_FAILURE_TTL_SECONDS,
                retry=Retry(max=2, interval=[2, 5])
            )
            logger.info("job_enqueued", job_id=job_id, document_id=document_id)
        except Exception as e:
            logger.error("queue_enqueue_failed", job_id=job_id, error=str(e))
            raise QueueError(f"Failed to enqueue job {job_id}") from e

    def enqueue_document_processing_job(self, processing_job_id: str, document_id: str, request_id: str = None):
        try:
            self.processing_queue.enqueue(
                'app.processing_worker_main.process_document',
                kwargs={'processing_job_id': processing_job_id, 'document_id': document_id, 'request_id': request_id},
                job_id=processing_job_id,
                job_timeout=settings.PROCESSING_JOB_TIMEOUT_SECONDS,
                result_ttl=settings.RQ_RESULT_TTL_SECONDS,
                failure_ttl=settings.RQ_FAILURE_TTL_SECONDS,
                retry=Retry(max=2, interval=[2, 5])
            )
            logger.info("processing_job_enqueued", processing_job_id=processing_job_id, document_id=document_id)
        except Exception as e:
            logger.error("processing_queue_enqueue_failed", processing_job_id=processing_job_id, error=str(e))
            raise QueueError(f"Failed to enqueue processing job {processing_job_id}") from e

    def enqueue_indexing_job(self, indexing_job_id: str, document_id: str, request_id: str = None):
        try:
            self.indexing_queue.enqueue(
                'app.indexing_worker_main.process_indexing',
                kwargs={'indexing_job_id': indexing_job_id, 'document_id': document_id, 'request_id': request_id},
                job_id=indexing_job_id,
                job_timeout=settings.INDEXING_JOB_TIMEOUT_SECONDS,
                result_ttl=settings.RQ_RESULT_TTL_SECONDS,
                failure_ttl=settings.RQ_FAILURE_TTL_SECONDS,
                retry=Retry(max=2, interval=[2, 5])
            )
            logger.info("indexing_job_enqueued", indexing_job_id=indexing_job_id, document_id=document_id)
        except Exception as e:
            logger.error("indexing_queue_enqueue_failed", indexing_job_id=indexing_job_id, error=str(e))
            raise QueueError(f"Failed to enqueue indexing job {indexing_job_id}") from e

    def enqueue_account_deletion_job(self, deletion_job_id: str, request_id: str = None):
        try:
            existing = self.account_deletion_queue.fetch_job(deletion_job_id)
            if existing and existing.get_status(refresh=True) in {"queued", "started", "deferred", "scheduled"}:
                return existing
            if existing:
                existing.delete()
            job = self.account_deletion_queue.enqueue(
                "app.auth.worker.process_account_deletion",
                kwargs={"deletion_job_id": deletion_job_id, "request_id": request_id},
                job_id=deletion_job_id,
                job_timeout="2h",
                result_ttl=settings.RQ_RESULT_TTL_SECONDS,
                failure_ttl=settings.RQ_FAILURE_TTL_SECONDS,
                retry=Retry(max=3, interval=[2, 5, 15]),
            )
            logger.info("account_deletion_job_enqueued", deletion_job_id=deletion_job_id)
            return job
        except Exception as e:
            logger.error("account_deletion_enqueue_failed", deletion_job_id=deletion_job_id, error_type=type(e).__name__)
            raise QueueError(f"Failed to enqueue account deletion job {deletion_job_id}") from e

    def enqueue_document_gc(self, document_id: str, request_id: str = None):
        rq_job_id = f"document-gc-{document_id}"
        try:
            existing = self.document_gc_queue.fetch_job(rq_job_id)
            if existing and existing.get_status(refresh=True) in {"queued", "started", "deferred", "scheduled"}:
                return existing
            if existing:
                existing.delete()
            return self.document_gc_queue.enqueue(
                "app.auth.worker.process_document_gc",
                kwargs={"document_id": document_id, "request_id": request_id},
                job_id=rq_job_id,
                job_timeout="2h",
                result_ttl=settings.RQ_RESULT_TTL_SECONDS,
                failure_ttl=settings.RQ_FAILURE_TTL_SECONDS,
                retry=Retry(max=3, interval=[2, 5, 15]),
            )
        except Exception as e:
            logger.error("document_gc_enqueue_failed", document_id=document_id, error_type=type(e).__name__)
            raise QueueError(f"Failed to enqueue document GC {document_id}") from e

rq_client = RQClient()
