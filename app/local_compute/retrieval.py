"""Synchronous exact local retrieval over INDEX_READY SQLite artifacts."""
from __future__ import annotations
import json, math, re, sqlite3
import numpy as np
from app.retrieval.query_embedder import QueryEmbedder
from .errors import LocalComputeError, LocalComputeErrorCode

class LocalRetrievalStore:
    TOP_DENSE=50; TOP_LEXICAL=50; TOP_FINAL=10; RRF_K=60
    def __init__(self,settings,catalog): self.settings,self.catalog=settings,catalog
    def query_document_set(self,query_text,document_ids=None):
        if not isinstance(query_text,str) or not query_text.strip(): raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST)
        try:q=QueryEmbedder.get_instance().encode(query_text)
        except Exception as exc: raise LocalComputeError(LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE) from exc
        requested=document_ids or self._queryable_ids(); merged={}
        for doc_id in requested:
            doc=self._doc(doc_id)
            if doc['preparation_state']!='INDEX_READY': raise LocalComputeError(LocalComputeErrorCode.CAPABILITY_UNAVAILABLE,'Document is not locally queryable.')
            with sqlite3.connect(self.settings.data_root/self._artifact(doc['active_artifact_id'])) as db:
                rows=db.execute('SELECT c.id,c.document_id,c.legal_unit_id,c.content_text,c.metadata_json,c.provenance_json,e.dimension,e.normalized,e.index_version,e.vector FROM chunks c JOIN chunk_embeddings e ON e.chunk_id=c.id').fetchall()
                dense=[]
                for r in rows:
                    v=np.frombuffer(r[9],dtype=np.float32)
                    if r[6]!=768 or r[7]!=1 or r[8]!='block3-v1' or len(r[9])!=3072 or not np.isfinite(v).all() or not math.isclose(float(np.linalg.norm(v)),1,abs_tol=1e-4): raise LocalComputeError(LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR,'Invalid local vector.')
                    dense.append((float(np.dot(q,v)),r))
                dense.sort(key=lambda x:(-x[0],x[1][0]))
                for rank,(score,r) in enumerate(dense[:self.TOP_DENSE],1): merged.setdefault(r[0],[r,None,None,None,None])[1:3]=[score,rank]
                terms=self._terms(query_text)
                if terms:
                    match=' OR '.join('"'+t.replace('"','')+'"' for t in terms)
                    for rank,(cid,bm) in enumerate(db.execute('SELECT chunk_id,bm25(chunk_fts) FROM chunk_fts WHERE chunk_fts MATCH ? ORDER BY bm25(chunk_fts),chunk_id LIMIT ?',(match,self.TOP_LEXICAL)),1):
                        row=next((x for x in rows if x[0]==cid),None)
                        if row: merged.setdefault(cid,[row,None,None,None,None])[3:5]=[float(-bm),rank]
        fused=[]
        for cid,(r,ds,dr,ls,lr) in merged.items(): fused.append((sum(1/(self.RRF_K+x) for x in (dr,lr) if x),cid,r,ds,dr,ls,lr))
        fused.sort(key=lambda x:(-x[0],x[1])); return [self._result(v,i) for i,v in enumerate(fused[:self.TOP_FINAL],1)]
    @staticmethod
    def _terms(text): return list(dict.fromkeys(re.findall(r'[\wÀ-ỹ]+',text.casefold())))
    def _result(self,v,rank):
        score,cid,r,ds,dr,ls,lr=v; return {'chunk_id':cid,'document_id':r[1],'legal_unit_id':r[2],'content_text':r[3],'metadata_json':json.loads(r[4]),'provenance_json':json.loads(r[5]),'dense_score':ds,'dense_rank':dr,'lexical_score':ls,'lexical_rank':lr,'fusion_score':score,'final_rank':rank}
    def _queryable_ids(self):
        with self.catalog._connect() as c:return [r[0] for r in c.execute("SELECT document_id FROM local_documents WHERE preparation_state='INDEX_READY'")]
    def _doc(self,id):
        with self.catalog._connect() as c:r=c.execute('SELECT document_id,preparation_state,active_artifact_id FROM local_documents WHERE document_id=?',(id,)).fetchone()
        if not r: raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_NOT_FOUND)
        return dict(zip(('document_id','preparation_state','active_artifact_id'),r))
    def _artifact(self,id):
        with self.catalog._connect() as c:r=c.execute('SELECT relative_path FROM local_artifacts WHERE artifact_id=?',(id,)).fetchone()
        if not r: raise LocalComputeError(LocalComputeErrorCode.CAPABILITY_UNAVAILABLE)
        return r[0]+'/artifact.sqlite3'
