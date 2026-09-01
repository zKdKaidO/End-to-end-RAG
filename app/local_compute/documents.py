"""Managed source-PDF acceptance; byte streams only, never caller paths."""
from __future__ import annotations
import hashlib, os, time, unicodedata, uuid
from collections.abc import Iterable
from app.pdf.validator import validate_and_hash_pdf
from .catalog import LocalCatalog
from .errors import LocalComputeError, LocalComputeErrorCode
from .settings import LocalComputeSettings

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
    def source_path(self, document_id: str):
        doc=self.get(document_id)
        if not doc: raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_NOT_FOUND)
        return self.settings.data_root / doc["source_relative_path"]
    @staticmethod
    def _hash_file(path):
        d=hashlib.sha256()
        with path.open("rb") as h:
            for block in iter(lambda:h.read(1024*1024),b""): d.update(block)
        return d.hexdigest()
