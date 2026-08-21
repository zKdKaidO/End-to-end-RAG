from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
import uuid

from app.db.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.repositories.indexing_job_repo import IndexingJobRepository
from app.indexing.constants import CANONICAL_INDEX_VERSION

router = APIRouter(tags=['indexing'])

@router.post('/documents/{document_id}/index', status_code=202)
def create_index(document_id: str, db: Session = Depends(get_db)):
    repo = IndexingJobRepository(db)
    
    # Frozen block 3 model config
    embedding_model = 'intfloat/multilingual-e5-base'
    
    try:
        job = repo.create_job(document_id, CANONICAL_INDEX_VERSION, embedding_model)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    job_id = str(job.id)
    request_id = str(uuid.uuid4())
    
    from redis import Redis
    from rq import Queue, Retry
    from app.core.config import settings
    
    raw_redis = Redis.from_url(settings.REDIS_URL)
    q = Queue('document-indexing', connection=raw_redis)
    from app.indexing_worker_main import process_indexing
    
    try:
        q.enqueue(
            process_indexing,
            kwargs={'indexing_job_id': job_id, 'document_id': document_id, 'request_id': request_id},
            job_id=job_id,
            retry=Retry(max=2, interval=[2, 5])
        )
    except Exception as e:
        repo.mark_failed(job_id, "QUEUE", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="Failed to enqueue indexing job")
    
    return {'job_id': job_id, 'status': 'PENDING'}

@router.get('/indexing-jobs/{job_id}')
def get_index_job(job_id: str, db: Session = Depends(get_db)):
    repo = IndexingJobRepository(db)
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid job_id')
        
    job = repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
        
    return {
        'job_id': str(job.id),
        'document_id': str(job.document_id),
        'status': job.status,
        'current_stage': job.current_stage,
        'chunks_total': job.chunks_total,
        'chunks_indexed': job.chunks_indexed,
        'embedding_model': job.embedding_model,
        'index_version': job.index_version,
        'error_stage': job.error_stage,
        'error_type': job.error_type,
        'error_message': job.error_message,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.finished_at.isoformat() if job.finished_at else None
    }

@router.get('/documents/{document_id}/indexing-status')
def get_indexing_status(document_id: str, db: Session = Depends(get_db)):
    repo = IndexingJobRepository(db)
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid document_id')
        
    jobs = db.execute(text("SELECT id FROM indexing_jobs WHERE document_id = :did ORDER BY created_at DESC LIMIT 1"), {"did": document_id}).fetchone()
    if not jobs:
        raise HTTPException(status_code=404, detail='No indexing job found for document')
        
    job = repo.get_by_id(str(jobs[0]))
    return {
        'job_id': str(job.id),
        'status': job.status,
        'current_stage': job.current_stage,
        'chunks_total': job.chunks_total,
        'chunks_indexed': job.chunks_indexed
    }

@router.get('/documents/{document_id}/indexes')
def get_document_indexes(document_id: str, db: Session = Depends(get_db)):
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid document_id')
        
    indexes = db.execute(text("""
        SELECT id, chunk_id, document_id, embedding_dimension, embedding_model, index_version, (lexical_tsv IS NOT NULL) as lexical_index_present,
               vector_norm(embedding) as norm
        FROM chunk_indexes
        WHERE document_id = :did
    """), {"did": document_id}).fetchall()
    
    return [
        {
            'id': str(r[0]),
            'chunk_id': str(r[1]),
            'document_id': str(r[2]),
            'embedding_dimension': r[3],
            'embedding_model': r[4],
            'index_version': r[5],
            'lexical_index_present': r[6],
            'embedding_norm': float(r[7]) if r[7] is not None else None
        } for r in indexes
    ]
