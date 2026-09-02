"""Canonical E5 indexing for a prepared local artifact; no retrieval surface."""
from __future__ import annotations
import math, sqlite3, time, uuid
import numpy as np
from app.indexing.embedder import E5Embedder
from .errors import LocalComputeError, LocalComputeErrorCode
from .jobs import LocalJobStore

class LocalIndexService:
    def __init__(self, settings, catalog): self.settings,self.catalog=settings,catalog; self.jobs=LocalJobStore(catalog)
    def index_document(self, document_id):
        with self.catalog.document_lock(document_id):
            return self._index_document_locked(document_id)
    def _index_document_locked(self, document_id):
        doc=self._document(document_id)
        if doc['preparation_state'] not in ('PREPARED_NOT_INDEXED','INDEX_READY'): raise LocalComputeError(LocalComputeErrorCode.CAPABILITY_UNAVAILABLE)
        artifact_id=doc['active_artifact_id']; job=self.jobs.enqueue_skeleton('INDEX_DOCUMENT')
        with self.catalog._connect() as c:c.execute("UPDATE local_jobs SET document_id=?,artifact_id=?,stage='INDEXING',state='RUNNING' WHERE job_id=?",(document_id,artifact_id,job));c.execute("UPDATE local_documents SET preparation_state='INDEXING' WHERE document_id=?",(document_id,))
        try:
            try: embedder=E5Embedder.get_instance()
            except Exception as exc: raise LocalComputeError(LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE) from exc
            path=self.settings.data_root/self._artifact_path(artifact_id)
            with sqlite3.connect(path) as db:
                rows=db.execute('SELECT id,embedding_text FROM chunks ORDER BY chunk_index').fetchall()
                vectors=embedder.encode_batch(rows)
                if len(vectors)!=len(rows): raise LocalComputeError(LocalComputeErrorCode.PREPARATION_FAILED)
                db.execute('BEGIN IMMEDIATE'); db.execute('CREATE TABLE IF NOT EXISTS chunk_embeddings(chunk_id TEXT PRIMARY KEY REFERENCES chunks(id),model TEXT NOT NULL,dimension INTEGER NOT NULL,normalized INTEGER NOT NULL,index_version TEXT NOT NULL,vector BLOB NOT NULL CHECK(length(vector)=3072))');db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(chunk_id UNINDEXED,content_text)');db.execute('DELETE FROM chunk_embeddings');db.execute('DELETE FROM chunk_fts')
                for (chunk_id,_), vector in zip(rows,vectors):
                    v=np.asarray(vector,dtype=np.float32)
                    if v.shape!=(768,) or not np.isfinite(v).all() or not math.isclose(float(np.linalg.norm(v)),1.0,abs_tol=1e-4): raise LocalComputeError(LocalComputeErrorCode.PREPARATION_FAILED)
                    db.execute('INSERT INTO chunk_embeddings VALUES(?,?,?,?,?,?)',(chunk_id,embedder.model_name,768,1,'block3-v1',v.tobytes(order='C')))
                db.execute('INSERT INTO chunk_fts SELECT id,content_text FROM chunks')
                self._validate(db,len(rows),embedder.model_name); db.execute("INSERT OR REPLACE INTO artifact_metadata VALUES('index_state','INDEX_READY')");db.commit()
            with self.catalog._connect() as c:c.execute("UPDATE local_documents SET preparation_state='INDEX_READY',last_error_code=NULL,updated_at=? WHERE document_id=?",(int(time.time()),document_id))
            self.jobs.update(job,'SUCCEEDED','INDEX_READY',100); return {'job_id':job,'document_id':document_id,'artifact_id':artifact_id,'index_state':'INDEX_READY','embedding_count':len(rows)}
        except LocalComputeError as exc:
            with self.catalog._connect() as c:c.execute("UPDATE local_documents SET preparation_state='PREPARED_NOT_INDEXED',last_error_code=? WHERE document_id=?",(exc.code.value,document_id))
            self.jobs.update(job,'FAILED','FAILED',100,exc.code.value); raise
    def _validate(self,db,count,model):
        if db.execute('SELECT COUNT(*) FROM chunk_embeddings').fetchone()[0]!=count or db.execute('SELECT COUNT(*) FROM chunk_fts').fetchone()[0]!=count: raise LocalComputeError(LocalComputeErrorCode.PREPARATION_FAILED)
        for dim,norm,name,blob in db.execute('SELECT dimension,normalized,model,vector FROM chunk_embeddings'):
            v=np.frombuffer(blob,dtype=np.float32)
            if dim!=768 or norm!=1 or name!=model or len(blob)!=3072 or not np.isfinite(v).all() or not math.isclose(float(np.linalg.norm(v)),1,abs_tol=1e-4): raise LocalComputeError(LocalComputeErrorCode.PREPARATION_FAILED)
    def _document(self,id):
        with self.catalog._connect() as c:r=c.execute('SELECT document_id,preparation_state,active_artifact_id FROM local_documents WHERE document_id=?',(id,)).fetchone()
        if not r: raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_NOT_FOUND)
        return dict(zip(('document_id','preparation_state','active_artifact_id'),r))
    def _artifact_path(self,id):
        with self.catalog._connect() as c:r=c.execute('SELECT relative_path FROM local_artifacts WHERE artifact_id=?',(id,)).fetchone()
        if not r: raise LocalComputeError(LocalComputeErrorCode.CAPABILITY_UNAVAILABLE)
        return r[0]+'/artifact.sqlite3'
