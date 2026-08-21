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

    def enqueue_ingestion_job(self, job_id: str, document_id: str, request_id: str = None):
        try:
            self.queue.enqueue(
                'app.worker_main.process_ingestion',
                kwargs={'job_id': job_id, 'document_id': document_id, 'request_id': request_id},
                job_id=job_id,
                job_timeout='1h',
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
                job_timeout='2h',
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
                job_timeout='2h',
                retry=Retry(max=2, interval=[2, 5])
            )
            logger.info("indexing_job_enqueued", indexing_job_id=indexing_job_id, document_id=document_id)
        except Exception as e:
            logger.error("indexing_queue_enqueue_failed", indexing_job_id=indexing_job_id, error=str(e))
            raise QueueError(f"Failed to enqueue indexing job {indexing_job_id}") from e

rq_client = RQClient()
