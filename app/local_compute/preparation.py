"""Local-only Block 1/2 preparation wrapper; intentionally excludes embeddings."""
from __future__ import annotations
import hashlib, json, os, shutil, sqlite3, time, uuid
from pathlib import Path
from app.pdf.extractor import PDFExtractor
from app.processing.cleaner import PageCleaner
from app.processing.header_footer import HeaderFooterRemover
from app.processing.reconstruction import DocumentReconstructor
from app.processing.metadata_extractor import MetadataExtractor
from app.processing.parser import LegalParser
from app.processing.chunker import Chunker
from .documents import LocalDocumentStore
from .errors import LocalComputeError, LocalComputeErrorCode
from .jobs import LocalJobStore
from .settings import LocalComputeSettings

ARTIFACT_SCHEMA_VERSION=1
ARTIFACT_PROFILE_ID="zkd-local-artifact-v1"
def artifact_fingerprint():
    payload={"schema":1,"parser":"block2-v1","chunking":"block2-token-safe-v1","embedding_model":"intfloat/multilingual-e5-base","dimension":768,"normalized":True,"passage_prefix":"passage: ","query_prefix":"query: ","token_limit":512,"index_version":"block3-v1","retrieval_store":"sqlite-v1","hierarchy":"legal-units-v1"}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class LocalPreparationService:
    def __init__(self, settings: LocalComputeSettings, catalog):
        self.settings,self.catalog=settings,catalog; self.documents=LocalDocumentStore(settings,catalog); self.jobs=LocalJobStore(catalog)
    def prepare(self, document_id: str) -> dict:
        with self.catalog.document_lock(document_id):
            return self._prepare_locked(document_id)
    def _prepare_locked(self, document_id: str) -> dict:
        document=self.documents.get(document_id)
        if not document: raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_NOT_FOUND)
        artifact_id=str(uuid.uuid4()); job_id=self.jobs.enqueue_preparation(document_id,artifact_id)
        staging=self.settings.artifacts_path/document_id/f"{artifact_id}.staging"; final=self.settings.artifacts_path/document_id/artifact_id
        try:
            self._update_doc(document_id,"PROCESSING"); self.jobs.update(job_id,"RUNNING","PROCESSING",5)
            staging.mkdir(parents=True,exist_ok=False)
            pages=list(PDFExtractor.extract_pages(self.documents.source_path(document_id).read_bytes()))
            cleaned=HeaderFooterRemover().remove_headers_footers([PageCleaner().clean(p["raw_text"]) for p in pages])
            normalized,offsets=DocumentReconstructor().reconstruct(cleaned)
            if not normalized.strip(): raise LocalComputeError(LocalComputeErrorCode.UNSUPPORTED_TEXTLESS_PDF,"Text-native PDF content is required.")
            self._cancel_if_requested(job_id); self.jobs.update(job_id,"RUNNING","CHUNKING",45); self._update_doc(document_id,"CHUNKING")
            metadata=MetadataExtractor().extract(normalized); units=LegalParser().parse(normalized)
            try: chunks=Chunker().generate_chunks(normalized,units,metadata)
            except OSError as exc: raise LocalComputeError(LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE,"Canonical E5 tokenizer artifact is unavailable.") from exc
            if not chunks: raise LocalComputeError(LocalComputeErrorCode.PREPARATION_FAILED,"No valid chunks were created.")
            self._enrich(chunks,metadata,document_id,offsets); self._map_units(units,offsets)
            self._cancel_if_requested(job_id); self.jobs.update(job_id,"RUNNING","VALIDATING",75); self._update_doc(document_id,"VALIDATING")
            artifact_db=staging/"artifact.sqlite3"; self._persist(artifact_db,document,artifact_id,pages,normalized,offsets,units,chunks,metadata)
            self._validate(artifact_db,document,artifact_id)
            os.replace(staging,final)
            integrity=self._hash_file(final/"artifact.sqlite3"); now=int(time.time())
            with self.catalog._connect() as db:
                db.execute("INSERT INTO local_artifacts(artifact_id,document_id,profile_id,profile_fingerprint,relative_path,state,integrity_hash,page_count,chunk_count,created_at,promoted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(artifact_id,document_id,ARTIFACT_PROFILE_ID,artifact_fingerprint(),str(final.relative_to(self.settings.data_root)),"PREPARED_NOT_INDEXED",integrity,len(pages),len(chunks),now,now))
                db.execute("UPDATE local_documents SET active_artifact_id=?,preparation_state='PREPARED_NOT_INDEXED',last_error_code=NULL,updated_at=? WHERE document_id=?",(artifact_id,now,document_id))
            self.jobs.update(job_id,"SUCCEEDED","PREPARED_NOT_INDEXED",100)
            return {"job_id":job_id,"document_id":document_id,"artifact_id":artifact_id,"preparation_state":"PREPARED_NOT_INDEXED","page_count":len(pages),"chunk_count":len(chunks)}
        except LocalComputeError as exc:
            if staging.exists(): shutil.rmtree(staging)
            state="CANCELLED" if exc.code==LocalComputeErrorCode.JOB_CANCELLED else "FAILED"; self.jobs.update(job_id,state,state,100,exc.code.value)
            if not document.get("active_artifact_id"): self._update_doc(document_id,"FAILED",exc.code.value)
            raise
        except Exception as exc:
            if staging.exists(): shutil.rmtree(staging)
            self.jobs.update(job_id,"FAILED","FAILED",100,"PREPARATION_FAILED")
            if not document.get("active_artifact_id"): self._update_doc(document_id,"FAILED","PREPARATION_FAILED")
            raise LocalComputeError(LocalComputeErrorCode.PREPARATION_FAILED,"Local preparation failed.") from exc
    def _update_doc(self, doc,state,error=None):
        with self.catalog._connect() as db: db.execute("UPDATE local_documents SET preparation_state=?,last_error_code=?,updated_at=? WHERE document_id=?",(state,error,int(time.time()),doc))
    def _cancel_if_requested(self, job):
        if self.jobs.is_cancel_requested(job): raise LocalComputeError(LocalComputeErrorCode.JOB_CANCELLED)
    @staticmethod
    def _page(offset, offsets):
        for item in offsets:
            if item["char_start"]<=offset<=item["char_end"]: return item["page_number"]
        return offsets[-1]["page_number"] if offsets else -1
    def _enrich(self,chunks,metadata,doc,offsets):
        for c in chunks:
            c["metadata_json"]=metadata; c["page_start"]=self._page(c["char_start"],offsets); c["page_end"]=self._page(max(c["char_start"],c["char_end"]-1),offsets)
            c["provenance_json"]={"document_id":doc,"page_start":c["page_start"],"page_end":c["page_end"],"char_start":c["char_start"],"char_end":c["char_end"],**({"split":c["split"]} if "split" in c else {})}
    def _map_units(self,units,offsets):
        for u in units:
            u.local_id=str(uuid.uuid4()); u.page_start=self._page(u.start_char,offsets); u.page_end=self._page(u.end_char,offsets); self._map_units(u.children,offsets)
    def _persist(self,path,doc,artifact_id,pages,text,offsets,units,chunks,metadata):
        with sqlite3.connect(path) as db:
            db.execute("PRAGMA foreign_keys=ON"); db.executescript("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY); INSERT INTO schema_migrations VALUES(1); CREATE TABLE artifact_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE pages(page_number INTEGER PRIMARY KEY,raw_text TEXT NOT NULL,char_count INTEGER NOT NULL); CREATE TABLE reconstruction(id INTEGER PRIMARY KEY CHECK(id=1),normalized_text TEXT NOT NULL,page_offset_map TEXT NOT NULL); CREATE TABLE legal_units(id TEXT PRIMARY KEY,parent_id TEXT REFERENCES legal_units(id),unit_type TEXT,unit_number TEXT,unit_title TEXT,char_start INTEGER,char_end INTEGER,page_start INTEGER,page_end INTEGER,level INTEGER); CREATE TABLE chunks(id TEXT PRIMARY KEY,document_id TEXT,legal_unit_id TEXT REFERENCES legal_units(id),chunk_index INTEGER UNIQUE,content_text TEXT,embedding_text TEXT,token_count INTEGER,page_start INTEGER,page_end INTEGER,metadata_json TEXT,provenance_json TEXT);")
            meta={"artifact_id":artifact_id,"profile_id":ARTIFACT_PROFILE_ID,"profile_fingerprint":artifact_fingerprint(),"source_sha256":doc["content_sha256"],"document_id":doc["document_id"],"state":"PREPARED_NOT_INDEXED","metadata":json.dumps(metadata,ensure_ascii=False)}
            db.executemany("INSERT INTO artifact_metadata VALUES (?,?)",meta.items()); db.executemany("INSERT INTO pages VALUES (?,?,?)",[(p["page_number"],p["raw_text"],p["char_count"]) for p in pages]); db.execute("INSERT INTO reconstruction VALUES(1,?,?)",(text,json.dumps(offsets)))
            def put(u,parent=None):
                db.execute("INSERT INTO legal_units VALUES(?,?,?,?,?,?,?,?,?,?)",(u.local_id,parent,u.unit_type,u.unit_number,u.title,u.start_char,u.end_char,u.page_start,u.page_end,u.level))
                for child in u.children: put(child,u.local_id)
            for unit in units: put(unit)
            db.executemany("INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?,?,?)",[(str(uuid.uuid4()),doc["document_id"],c["legal_unit"].local_id,c["chunk_index"],c["content_text"],c["embedding_text"],Chunker().input_contract.count_final_tokens(c["embedding_text"]),c["page_start"],c["page_end"],json.dumps(c["metadata_json"],ensure_ascii=False),json.dumps(c["provenance_json"],ensure_ascii=False)) for c in chunks])
    def _validate(self,path,doc,artifact_id):
        with sqlite3.connect(path) as db:
            schema=db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]; chunks=db.execute("SELECT COUNT(*),COUNT(DISTINCT chunk_index) FROM chunks").fetchone(); profile=dict(db.execute("SELECT key,value FROM artifact_metadata").fetchall())
            if schema!=ARTIFACT_SCHEMA_VERSION or chunks[0]==0 or chunks[0]!=chunks[1] or profile.get("source_sha256")!=doc["content_sha256"] or profile.get("profile_fingerprint")!=artifact_fingerprint(): raise LocalComputeError(LocalComputeErrorCode.PREPARATION_FAILED,"Artifact validation failed.")
    @staticmethod
    def _hash_file(path):
        d=hashlib.sha256();
        with path.open("rb") as h:
            for b in iter(lambda:h.read(1024*1024),b""):d.update(b)
        return d.hexdigest()
