# To ensure Alembic discovers all models, import them here
from app.db.base import Base
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.document_page import DocumentPage
from app.models.document_processing_job import DocumentProcessingJob, ProcessingStage
from app.models.document_reconstruction import DocumentReconstruction
from app.models.legal_unit import LegalUnit
from app.models.chunk import Chunk
from app.models.indexing_job import IndexingJob
from app.models.chunk_index import ChunkIndex
from app.models.chat import ChatSession, ChatTurn, ChatMessage, MessageCitationSnapshot
from app.models.auth import (
    User, AuthSession, DocumentAccessGrant, GlobalDocumentAccess,
    AccountDeletionJob, AccountDeletionDocumentRef,
)
from app.models.compute_control import (
    ComputeDevice, ComputePairingChallenge, ComputePresence,
    LocalDocumentManifest, ComputeReplayNonce, ComputeLocalSessionGrant,
)

__all__ = [
    "Base", 
    "Document", 
    "IngestionJob", 
    "DocumentPage",
    "DocumentProcessingJob",
    "ProcessingStage",
    "DocumentReconstruction",
    "LegalUnit",
    "Chunk",
    "IndexingJob",
    "ChunkIndex",
    "ChatSession",
    "ChatTurn",
    "ChatMessage",
    "MessageCitationSnapshot",
    "User",
    "AuthSession",
    "DocumentAccessGrant",
    "GlobalDocumentAccess",
    "AccountDeletionJob",
    "AccountDeletionDocumentRef",
    "ComputeDevice",
    "ComputePairingChallenge",
    "ComputePresence",
    "LocalDocumentManifest",
    "ComputeReplayNonce",
    "ComputeLocalSessionGrant",
]
