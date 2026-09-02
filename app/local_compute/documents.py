"""Managed source-PDF acceptance; byte streams only, never caller paths."""
from __future__ import annotations
import hashlib, os, shutil, time, unicodedata, uuid
from collections.abc import Iterable
from app.pdf.validator import validate_and_hash_pdf
from .catalog import LocalCatalog
from .errors import LocalComputeError, LocalComputeErrorCode
from .settings import LocalComputeSettings
from .jobs import LocalJobStore

class LocalDocumentStore:
    def __init__(self, settings: LocalComputeSettings, catalog: LocalCatalog): self.settings, self.catalog = settings, catalog
    def accept_document(self, document_id: str, chunks: Iterable[bytes], filename: str, mime_type: str) -> dict:
        try: uuid.UUID(document_id)
        except ValueError as exc: raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "document_id must be a UUID.") from exc
        temporary, digest, total = self.settings.tmp_path / f"{uuid.uuid4()}.source.staging", hashlib.sha256(), 0
        try:
            with temporary.open("xb") as out:
                for chunk in chunks:
                    total += len(chunk)
                    if total > self.settings.source_pdf_max_bytes: raise LocalComputeError(LocalComputeErrorCode.PAYLOAD_TOO_LARGE)
                    digest.update(chunk); out.write(chunk)
                out.flush(); os.fsync(out.fileno())
            sha = digest.hexdigest()
            try: _, validated_sha = validate_and_hash_pdf(temporary.read_bytes(), filename, mime_type)
            except Exception as exc: raise LocalComputeError(LocalComputeErrorCode.INVALID_PDF, "PDF admission failed.") from exc
            if sha != validated_sha: raise LocalComputeError(LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR, "Source integrity failed.")
            existing = self.get(document_id)
            if existing:
                if existing["content_sha256"] == sha: return {**existing, "idempotent": True}
                raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_CONFLICT, "Document identity already owns different bytes.")
            rel = f"documents/{document_id}/source.pdf"; final = self.settings.data_root / rel
            final.parent.mkdir(parents=True, exist_ok=False); os.replace(temporary, final)
            if self._hash_file(final) != sha: raise LocalComputeError(LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR, "Managed source verification failed.")
            now = int(time.time())
            with self.catalog._connect() as db: db.execute("INSERT INTO local_documents(document_id,content_sha256,original_filename,mime_type,byte_size,source_relative_path,preparation_state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (document_id,sha,unicodedata.normalize("NFC",filename),mime_type,total,rel,"ACCEPTED",now,now))
            return {"document_id":document_id,"content_sha256":sha,"byte_size":total,"preparation_state":"ACCEPTED","idempotent":False}
        finally:
            if temporary.exists(): temporary.unlink()
    def get(self, document_id: str) -> dict | None:
        fields=("document_id","content_sha256","original_filename","mime_type","byte_size","source_relative_path","preparation_state","active_artifact_id","last_error_code","created_at","updated_at")
        with self.catalog._connect() as db: row=db.execute(f"SELECT {','.join(fields)} FROM local_documents WHERE document_id=?",(document_id,)).fetchone()
        return dict(zip(fields,row)) if row else None
    def list_documents(self) -> list[dict]:
        fields=("document_id","original_filename","byte_size","preparation_state","last_error_code","created_at","updated_at","page_count","chunk_count")
        with self.catalog._connect() as db:
            rows=db.execute("SELECT d.document_id,d.original_filename,d.byte_size,d.preparation_state,d.last_error_code,d.created_at,d.updated_at,COALESCE(a.page_count,0),COALESCE(a.chunk_count,0) FROM local_documents d LEFT JOIN local_artifacts a ON a.artifact_id=d.active_artifact_id ORDER BY d.updated_at DESC,d.document_id ASC").fetchall()
        return [dict(zip(fields,row)) | {"index_state": self._index_state(row[3])} for row in rows]
    def delete_document(self, document_id: str) -> dict:
        try: uuid.UUID(document_id)
        except ValueError as exc: raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "document_id must be a UUID.") from exc
        with self.catalog.document_lock(document_id):
            document=self.get(document_id)
            if not document: raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_NOT_FOUND)
            cancelled=LocalJobStore(self.catalog).cancel_for_document(document_id)
            try:
                self._remove_managed_tree(self.settings.documents_path, document_id)
                self._remove_managed_tree(self.settings.artifacts_path, document_id)
            except OSError as exc:
                raise LocalComputeError(LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR, "Local document cleanup failed.") from exc
            with self.catalog._connect() as db:
                db.execute("DELETE FROM local_jobs WHERE document_id=?", (document_id,))
                db.execute("DELETE FROM local_artifacts WHERE document_id=?", (document_id,))
                db.execute("DELETE FROM local_documents WHERE document_id=?", (document_id,))
            self.catalog.enqueue_control_manifest({"document_id":document_id,"preparation_state":"DELETED","index_state":"DELETED","local_availability":"DELETED","chunk_count":0,"artifact_id":None,"artifact_version":None,"artifact_profile_fingerprint":None},int(time.time()))
            return {"document_id":document_id,"state":"DELETED","cancelled_job_count":cancelled}
    def source_path(self, document_id: str):
        doc=self.get(document_id)
        if not doc: raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_NOT_FOUND)
        return self.settings.data_root / doc["source_relative_path"]
    @staticmethod
    def _index_state(preparation_state: str) -> str:
        if preparation_state == "INDEX_READY": return "INDEX_READY"
        if preparation_state == "INDEXING": return "INDEXING"
        if preparation_state == "PREPARED_NOT_INDEXED": return "NOT_INDEXED"
        return "NOT_READY"
    @staticmethod
    def _remove_managed_tree(root, document_id: str) -> None:
        root_resolved=root.resolve()
        target=(root/document_id).resolve(strict=False)
        if target.parent != root_resolved:
            raise OSError("LOCAL_DOCUMENT_PATH_INVALID")
        if target.exists(): shutil.rmtree(target)
    @staticmethod
    def _hash_file(path):
        d=hashlib.sha256()
        with path.open("rb") as h:
            for block in iter(lambda:h.read(1024*1024),b""): d.update(block)
        return d.hexdigest()
