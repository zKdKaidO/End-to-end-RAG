import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.routes.indexing import create_index
from app.indexing.constants import CANONICAL_INDEX_VERSION
from app.processing_worker_main import enqueue_canonical_indexing


def test_manual_indexing_endpoint_creates_canonical_job() -> None:
    document_id = str(uuid.uuid4())
    job = SimpleNamespace(id=uuid.uuid4())

    with (
        patch("app.api.routes.indexing.IndexingJobRepository") as repository_type,
        patch("redis.Redis.from_url"),
        patch("rq.Queue") as queue_type,
    ):
        repository_type.return_value.create_job.return_value = job
        response = create_index(document_id, db=MagicMock())

    repository_type.return_value.create_job.assert_called_once_with(
        document_id,
        CANONICAL_INDEX_VERSION,
        "intfloat/multilingual-e5-base",
    )
    queue_type.return_value.enqueue.assert_called_once()
    assert response == {"job_id": str(job.id), "status": "PENDING"}


def test_automatic_block2_completion_creates_canonical_job() -> None:
    document_id = str(uuid.uuid4())
    job = SimpleNamespace(id=uuid.uuid4())
    db = MagicMock()

    with (
        patch("app.repositories.indexing_job_repo.IndexingJobRepository") as repository_type,
        patch("app.queue.rq_client.rq_client") as queue_client,
    ):
        repository_type.return_value.create_job.return_value = job
        returned = enqueue_canonical_indexing(document_id, "request-1", db)

    repository_type.assert_called_once_with(db)
    repository_type.return_value.create_job.assert_called_once_with(
        document_id,
        index_version=CANONICAL_INDEX_VERSION,
        embedding_model="intfloat/multilingual-e5-base",
    )
    queue_client.enqueue_indexing_job.assert_called_once_with(
        indexing_job_id=str(job.id),
        document_id=document_id,
        request_id="request-1",
    )
    assert returned is job
