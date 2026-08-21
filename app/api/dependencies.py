from fastapi import Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.storage.minio_client import minio_client, MinioClient
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository

def get_document_repo(db: Session = Depends(get_db)) -> DocumentRepository:
    return DocumentRepository(db)

def get_job_repo(db: Session = Depends(get_db)) -> JobRepository:
    return JobRepository(db)

def get_storage_client() -> MinioClient:
    return minio_client
