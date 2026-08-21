import os
import sys
import logging
import traceback
from datetime import datetime

import structlog
from rq import Worker, Queue
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from redis.exceptions import RedisError

from app.db.database import SessionLocal
from app.repositories.indexing_job_repo import IndexingJobRepository
from app.repositories.chunk_index_repo import ChunkIndexRepository
from app.indexing.embedder import E5Embedder, EmbeddingInputTooLongError
from app.queue.rq_client import rq_client
from rq import get_current_job
from sqlalchemy import func

logging.basicConfig(level=logging.INFO, format="%(message)s")
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger(__name__)

def process_indexing(document_id: str, indexing_job_id: str, request_id: str):
    logger.info("indexing_job_started", document_id=document_id, indexing_job_id=indexing_job_id, request_id=request_id)
    
    db: Session = SessionLocal()
    try:
        job_repo = IndexingJobRepository(db)
        chunk_idx_repo = ChunkIndexRepository(db)
        
        # Verify job is PENDING, transition to PROCESSING / LOAD_CHUNKS
        db_job = job_repo.get_by_id(indexing_job_id)
        if not db_job:
            raise ValueError(f"IndexingJob {indexing_job_id} not found")
            
        if db_job.status not in ("PENDING", "FAILED", "PROCESSING"):
            logger.warning("indexing_transition_skipped", document_id=document_id, indexing_job_id=indexing_job_id)
            return

        job_repo.transition_to_processing(indexing_job_id)
        
        # 1. LOAD_CHUNKS
        chunks = chunk_idx_repo.get_chunks_for_document(document_id)
        if not chunks:
            raise ValueError("No chunks found for document")
            
        chunks_total = len(chunks)
        job_repo.update_counts(indexing_job_id, chunks_total=chunks_total)
        
        # Initialize Embedder (loads model from cache if available)
        # Initialize Embedder (loads model from cache if available)
        from redis import Redis
        embedder = E5Embedder.get_instance()
        
        # 2. EMBEDDING
        job_repo.update_stage(indexing_job_id, "EMBEDDING")
        batch_size = int(os.environ.get("EMBEDDING_BATCH_SIZE", "16"))
        
        index_data = []
        for i in range(0, chunks_total, batch_size):
            batch = chunks[i:i + batch_size]
            chunks_with_ids = [(c.id, c.embedding_text) for c in batch]
            
            # Encode batch
            embeddings = embedder.encode_batch(chunks_with_ids)
            
            for chunk, embedding in zip(batch, embeddings):
                index_data.append({
                    "chunk_id": chunk.id,
                    "document_id": document_id,
                    "embedding": embedding,
                    "lexical_tsv": func.to_tsvector('simple', chunk.content_text),
                    "embedding_model": embedder.model_name,
                    "embedding_dimension": embedder.embedding_dimension,
                    "index_version": db_job.index_version
                })
        
        # 3. PERSIST_INDEX
        job_repo.update_stage(indexing_job_id, "PERSIST_INDEX")
        chunk_idx_repo.upsert_indexes(document_id, index_data)
        
        # Update counts
        chunks_indexed = chunk_idx_repo.count_indexed_chunks(document_id, db_job.index_version)
        job_repo.update_counts(indexing_job_id, chunks_indexed=chunks_indexed)
        
        # 4. FINALIZE
        job_repo.update_stage(indexing_job_id, "FINALIZE")
        
        chunk_idx_repo.validate_index_output(document_id, db_job.index_version, db_job.embedding_model, chunks_total)
            
        job_repo.mark_completed(indexing_job_id)
        logger.info("indexing_job_completed", document_id=document_id, indexing_job_id=indexing_job_id, request_id=request_id)
        
    except Exception as e:
        logger.error("indexing_job_failed", document_id=document_id, error=str(e), indexing_job_id=indexing_job_id, request_id=request_id, traceback=traceback.format_exc())
        
        is_retriable = isinstance(e, (OperationalError, RedisError, ConnectionError, TimeoutError))
        rq_job = get_current_job()
        
        if rq_job:
            logger.info(f"Checking retry conditions: is_retriable={is_retriable}, retries_left={getattr(rq_job, 'retries_left', None)}")
        if is_retriable and rq_job and getattr(rq_job, 'retries_left', 0) is not None and getattr(rq_job, 'retries_left', 0) > 0:
            logger.info("indexing_job_transient_failure_retrying", document_id=document_id, indexing_job_id=indexing_job_id, request_id=request_id, retries_left=rq_job.retries_left)
            raise 

        if rq_job:
            rq_job.retries_left = 0
            rq_job.save()
            
        failed_stage = "UNKNOWN"
        try:
            if 'job_repo' in locals() and indexing_job_id:
                latest_job = job_repo.get_by_id(indexing_job_id)
                if latest_job:
                    failed_stage = latest_job.current_stage
        except Exception as ex:
            logger.error(f"Failed to get latest job stage: {ex}")

        try:
            if 'job_repo' in locals() and indexing_job_id:
                job_repo.mark_failed(indexing_job_id, error_stage=failed_stage, error_type=type(e).__name__, error_message=str(e))
        except Exception as ex:
            logger.error(f"Failed to mark job as failed: {ex}")
            
        raise

    finally:
        db.close()

if __name__ == '__main__':
    redis_conn = rq_client.redis_conn
    # E5Embedder.get_instance()  # Preload model? No, wait until first job to avoid huge memory in parent?
    worker = Worker(['document-indexing'], connection=redis_conn, disable_default_exception_handler=True)
    worker.work(with_scheduler=True)
