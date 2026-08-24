import os
import sys
import traceback
from rq import Worker, Queue
from rq import get_current_job
from redis import Redis
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.database import SessionLocal
from app.models.document_processing_job import ProcessingStage
from app.indexing.constants import CANONICAL_INDEX_VERSION

logger = get_logger(__name__)


# Test-only deterministic pause immediately before the durable persistence
# boundary. Production leaves this unset.
LIFECYCLE_TEST_HOOK = None


def enqueue_canonical_indexing(document_id: str, request_id: str | None, db):
    """Create and enqueue the canonical Block 3 job after Block 2 completes."""
    from app.repositories.indexing_job_repo import IndexingJobRepository
    from app.queue.rq_client import rq_client

    from sqlalchemy import select
    from app.models.document import Document

    # Canonical GC uses the same lock. If deletion won after Block 2 commit,
    # indexing handoff is an expected no-op rather than a late FK write.
    db.rollback()
    document = db.scalar(
        select(Document).where(Document.id == document_id).with_for_update()
    )
    if document is None:
        db.rollback()
        logger.info("processing_index_handoff_skipped_target_deleted")
        return None

    repo = IndexingJobRepository(db)
    job = repo.create_job(
        document_id,
        index_version=CANONICAL_INDEX_VERSION,
        embedding_model="intfloat/multilingual-e5-base",
    )
    rq_client.enqueue_indexing_job(
        indexing_job_id=str(job.id),
        document_id=str(document_id),
        request_id=request_id,
    )
    return job


def _continue_processing(repo, processing_job_id: str, document_id: str, stage: ProcessingStage) -> bool:
    if repo.update_stage(processing_job_id, stage):
        return True
    if not repo.document_exists(document_id):
        repo.db.rollback()
        logger.info(
            "processing_aborted_target_deleted",
            lifecycle_reason="PROCESSING_ABORTED_TARGET_DELETED",
            attempted_stage=stage.value,
        )
        return False
    raise RuntimeError(
        f"Processing lifecycle conflict at {stage.value}: canonical document exists but active job transition failed"
    )

def process_document(processing_job_id: str, document_id: str, request_id: str = None):
    from structlog.contextvars import clear_contextvars, bind_contextvars
    clear_contextvars()
    if request_id:
        bind_contextvars(request_id=request_id)
    bind_contextvars(processing_job_id=processing_job_id, document_id=document_id)
    
    logger.info("processing_job_started")
    db = SessionLocal()

    try:
        from app.repositories.processing_job_repo import ProcessingJobRepository
        repo = ProcessingJobRepository(db)

        # Mark PROCESSING
        success = repo.transition_to_processing(processing_job_id)
        if not success:
            if not repo.document_exists(document_id):
                repo.db.rollback()
                logger.info(
                    "processing_aborted_target_deleted",
                    lifecycle_reason="PROCESSING_ABORTED_TARGET_DELETED",
                    attempted_stage="PROCESSING",
                )
                return
            raise RuntimeError("Processing lifecycle conflict: canonical document exists but job cannot start")
            
        if not _continue_processing(repo, processing_job_id, document_id, ProcessingStage.CLEANING):
            return
        
        # 1. Load Document Pages
        from app.models.document_page import DocumentPage
        pages = db.query(DocumentPage).filter(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number).all()
        page_texts = [p.raw_text for p in pages]
        
        # 2. Page Cleaning
        from app.processing.cleaner import PageCleaner
        cleaner = PageCleaner()
        cleaned_pages = [cleaner.clean(pt) for pt in page_texts]
        
        # 3. Header/Footer Removal
        if not _continue_processing(repo, processing_job_id, document_id, ProcessingStage.HEADER_FOOTER_REMOVAL):
            return
        from app.processing.header_footer import HeaderFooterRemover
        hf_remover = HeaderFooterRemover()
        hf_cleaned = hf_remover.remove_headers_footers(cleaned_pages)
        
        # 4. Reconstruction
        if not _continue_processing(repo, processing_job_id, document_id, ProcessingStage.RECONSTRUCTION):
            return
        from app.processing.reconstruction import DocumentReconstructor
        reconstructor = DocumentReconstructor()
        normalized_text, page_offset_map = reconstructor.reconstruct(hf_cleaned)
        
        # 5. Metadata Extraction
        if not _continue_processing(repo, processing_job_id, document_id, ProcessingStage.METADATA_EXTRACTION):
            return
        from app.processing.metadata_extractor import MetadataExtractor
        metadata_extractor = MetadataExtractor()
        metadata = metadata_extractor.extract(normalized_text)
        
        # 6. Legal Parsing
        if not _continue_processing(repo, processing_job_id, document_id, ProcessingStage.LEGAL_PARSING):
            return
        from app.processing.parser import LegalParser
        parser = LegalParser()
        units = parser.parse(normalized_text)
        
        # 7. Chunking
        if not _continue_processing(repo, processing_job_id, document_id, ProcessingStage.CHUNKING):
            return
        from app.processing.chunker import Chunker
        chunker = Chunker()
        chunk_dicts = chunker.generate_chunks(normalized_text, units, metadata)
        
        # 8. Provenance and Metadata Enrichment
        for c in chunk_dicts:
            c["metadata_json"] = metadata
            
            start_page = reconstructor.get_page_for_offset(c["char_start"], page_offset_map)
            end_page = reconstructor.get_page_for_offset(c["char_end"], page_offset_map)
            c["page_start"] = start_page
            c["page_end"] = end_page
            c["provenance_json"] = {
                "document_id": document_id,
                "page_start": start_page,
                "page_end": end_page
            }
            
        # Recursive page mapping for units
        def map_unit_pages(u):
            u.page_start = reconstructor.get_page_for_offset(u.start_char, page_offset_map)
            u.page_end = reconstructor.get_page_for_offset(u.end_char, page_offset_map)
            for child in u.children:
                map_unit_pages(child)
        for u in units:
            map_unit_pages(u)
            
        # 9. Persistence
        if not _continue_processing(repo, processing_job_id, document_id, ProcessingStage.PERSISTENCE):
            return
        if LIFECYCLE_TEST_HOOK is not None:
            LIFECYCLE_TEST_HOOK("BEFORE_PERSISTENCE", document_id, processing_job_id)
        from app.repositories.processing_repo import ProcessingRepository
        proc_repo = ProcessingRepository(db)
        
        outcome = proc_repo.save_processing_results(
            processing_job_id, document_id, normalized_text, page_offset_map, units, chunk_dicts
        )
        if outcome is None:
            logger.info(
                "processing_aborted_target_deleted",
                lifecycle_reason="PROCESSING_ABORTED_TARGET_DELETED",
                attempted_stage=ProcessingStage.PERSISTENCE.value,
            )
            return
        _units_created, _chunks_created, has_access_reference = outcome
        if not has_access_reference:
            logger.info(
                "processing_index_handoff_skipped_unreferenced",
                lifecycle_reason="PROCESSING_TARGET_HAS_NO_ACCESS_REFERENCE",
            )
            return

        # 10. Enqueue Indexing Job. Completion was committed atomically with
        # derived data under the lifecycle guard above.
        if enqueue_canonical_indexing(document_id, request_id, db) is None:
            return
        
        logger.info("processing_job_completed")
    except Exception as e:
        logger.error("processing_job_failed", error=str(e), traceback=traceback.format_exc())
        
        from sqlalchemy.exc import OperationalError
        from redis.exceptions import RedisError
        is_retriable = isinstance(e, (OperationalError, RedisError, ConnectionError, TimeoutError))
        
        rq_job = get_current_job()
        
        if rq_job:
            logger.info(f"Checking retry conditions: is_retriable={is_retriable}, retries_left={getattr(rq_job, 'retries_left', None)}")
        if is_retriable and rq_job and getattr(rq_job, 'retries_left', 0) is not None and getattr(rq_job, 'retries_left', 0) > 0:
            logger.info("processing_job_transient_failure_retrying", retries_left=rq_job.retries_left)
            raise # Let RQ retry
            
        # Terminal failure
        # To prevent RQ from retrying deterministic errors, we can manually set retries_left to 0 on the job
        if rq_job:
            rq_job.retries_left = 0
            rq_job.save()
            
        # We need to know which stage failed. We don't have it directly in memory without querying, 
        # but we can query it or use 'UNKNOWN'. 
        # Let's query it
        from app.repositories.processing_job_repo import ProcessingJobRepository
        repo = ProcessingJobRepository(db)
        
        db_job = repo.get_by_id(processing_job_id)
        failed_stage = db_job.current_stage if db_job else "UNKNOWN"
        
        repo.mark_failed(processing_job_id, error_stage=failed_stage, error_type=type(e).__name__, error_message=str(e))
        
        raise # Re-raise so RQ marks it as Failed (now with retries_left=0, it will go to failed registry)
    finally:
        db.close()

if __name__ == '__main__':
    setup_logging()
    redis_url = settings.REDIS_URL
    conn = Redis.from_url(redis_url)
    
    logger.info("Processing worker process starting up...", queues="document-processing")
    
    worker = Worker(['document-processing'], connection=conn)
    worker.work(with_scheduler=True)
