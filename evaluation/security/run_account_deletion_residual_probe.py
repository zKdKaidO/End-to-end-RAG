"""Controlled real-storage/RQ account-deletion residual audit."""

import hashlib
import json
import time
import uuid

import httpx
import pymupdf
from redis import Redis
from rq import Queue
from sqlalchemy import func, select

from app.auth.access import DocumentAccessService
from app.auth.service import AuthService
from app.chat.service import ChatHistoryService
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.auth import AccountDeletionJob, AuthSession, DocumentAccessGrant, User, UserRole
from app.models.chat import ChatSession
from app.models.document import Document, DocumentStatus
from app.storage.minio_client import minio_client


PASSWORD = "SecurityDeletionPassphrase!2026"
ORIGIN = "http://localhost:5173"


def pdf_bytes(label: str) -> bytes:
    document = pymupdf.open(); page = document.new_page(); page.insert_text((72, 72), label)
    payload = document.tobytes(); document.close(); return payload


def create_document(db, label: str) -> Document:
    payload = pdf_bytes(label)
    item = Document(
        filename=f"{label}.pdf",
        mime_type="application/pdf",
        file_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        status=DocumentStatus.COMPLETED,
    )
    db.add(item); db.commit(); db.refresh(item)
    item.storage_uri = minio_client.upload_pdf(str(item.id), payload)
    db.commit()
    return item


def main() -> None:
    suffix = uuid.uuid4().hex[:10]
    alice_email = f"security-delete-alice-{suffix}@example.invalid"
    bob_email = f"security-delete-bob-{suffix}@example.invalid"
    db = SessionLocal()
    shared_id = unique_id = bob_id = None
    job_id = None
    try:
        alice = AuthService(db).provision_user(alice_email, PASSWORD, UserRole.USER, must_change_password=False)
        bob = AuthService(db).provision_user(bob_email, PASSWORD, UserRole.USER, must_change_password=False)
        alice_id, bob_id = alice.id, bob.id
        unique = create_document(db, f"security-unique-{suffix}")
        shared = create_document(db, f"security-shared-{suffix}")
        unique_id, shared_id = unique.id, shared.id
        access = DocumentAccessService(db)
        access.grant_private(alice_id, unique_id)
        access.grant_private(alice_id, shared_id)
        access.grant_private(bob_id, shared_id)
        ChatHistoryService(db, alice_id).create_session("Security deletion history")

        with httpx.Client(base_url="http://127.0.0.1:8000", headers={"Origin": ORIGIN}, timeout=20) as client:
            login = client.post("/api/v1/auth/login", json={"email": alice_email, "password": PASSWORD})
            login.raise_for_status()
            response = client.request("DELETE", "/api/v1/auth/account", json={"password": PASSWORD})
            response.raise_for_status()
            job_id = uuid.UUID(response.json()["job_id"])

        deadline = time.monotonic() + 30
        state = None
        while time.monotonic() < deadline:
            db.expire_all()
            state = db.scalar(select(AccountDeletionJob.state).where(AccountDeletionJob.id == job_id))
            if state == "COMPLETED":
                break
            time.sleep(0.25)

        redis = Redis.from_url(settings.REDIS_URL)
        rq_job = Queue("account-deletion", connection=redis).fetch_job(str(job_id))
        result = {
            "job_state": state,
            "user_rows": db.scalar(select(func.count(User.id)).where(User.id == alice_id)),
            "auth_session_rows": db.scalar(select(func.count(AuthSession.id)).where(AuthSession.user_id == alice_id)),
            "grant_rows": db.scalar(select(func.count()).select_from(DocumentAccessGrant).where(DocumentAccessGrant.user_id == alice_id)),
            "chat_session_rows": db.scalar(select(func.count(ChatSession.id)).where(ChatSession.user_id == alice_id)),
            "unique_document_present": db.get(Document, unique_id) is not None,
            "unique_minio_present": minio_client.exists(str(unique_id)),
            "shared_document_present": db.get(Document, shared_id) is not None,
            "shared_minio_present": minio_client.exists(str(shared_id)),
            "bob_grant_present": db.get(DocumentAccessGrant, (shared_id, bob_id)) is not None,
            "rq_residual_status": rq_job.get_status(refresh=True) if rq_job else None,
        }
        print(json.dumps(result))
    finally:
        db.rollback()
        if shared_id:
            minio_client.delete(str(shared_id))
            shared = db.get(Document, shared_id)
            if shared:
                db.delete(shared)
        if unique_id and minio_client.exists(str(unique_id)):
            minio_client.delete(str(unique_id))
        if bob_id:
            bob = db.get(User, bob_id)
            if bob:
                db.delete(bob)
        db.commit()
        if job_id:
            queue = Queue("account-deletion", connection=Redis.from_url(settings.REDIS_URL))
            rq_job = queue.fetch_job(str(job_id))
            if rq_job:
                rq_job.delete()
        db.close()


if __name__ == "__main__":
    main()
