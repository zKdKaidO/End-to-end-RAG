"""Synchronous exact local retrieval over INDEX_READY SQLite artifacts."""
from __future__ import annotations
import json, math, re, sqlite3
import numpy as np
from app.indexing.embedder import E5Embedder
from app.retrieval.query_embedder import QueryEmbedder
from app.retrieval.hierarchy_expander import LegalHierarchyExpander
from app.retrieval.schemas import RetrievedCandidate
from .hierarchy import LocalHierarchyRepository
from .errors import LocalComputeError, LocalComputeErrorCode

class LocalRetrievalStore:
    TOP_DENSE=50; TOP_LEXICAL=50; TOP_FINAL=10; RRF_K=60
    def __init__(self,settings,catalog): self.settings,self.catalog=settings,catalog
    def query_document_set(self,query_text,document_ids=None):
        results, _ = self.query_document_set_with_diagnostics(query_text, document_ids)
        return results
    def query_document_set_with_diagnostics(self,query_text,document_ids=None):
        if not isinstance(query_text,str) or not query_text.strip(): raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST)
        try:
            embedder = E5Embedder.get_instance(
                cache_dir=str(self.settings.embedding_model_cache_dir),
                device="cpu",
            )
            q = QueryEmbedder(embedder).encode(query_text)
        except Exception as exc: raise LocalComputeError(LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE) from exc
        requested=document_ids or self._queryable_ids(); merged={}; document_artifacts={}
        for doc_id in requested:
            doc=self._doc(doc_id)
            if doc['preparation_state']!='INDEX_READY': raise LocalComputeError(LocalComputeErrorCode.CAPABILITY_UNAVAILABLE,'Document is not locally queryable.')
            document_artifacts[doc_id]=doc['active_artifact_id']
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
        fused.sort(key=lambda x:(-x[0],x[1]))
        base=[self._result(v,i,document_artifacts[r[1]]) for i,v in enumerate(fused[:self.TOP_FINAL],1)]
        candidates=[
            RetrievedCandidate.model_validate(
                {key: value for key, value in result.items() if key in RetrievedCandidate.model_fields}
            )
            for result in base
        ]
        expander=LegalHierarchyExpander(
            LocalHierarchyRepository(self.settings,self.catalog,document_artifacts),
            enabled=True,max_anchors=10,max_children_per_anchor=4,max_candidates_added=20,depth=1,
        )
        expanded, diagnostics=expander.expand(
            candidates,[self._uuid(document_id) for document_id in requested],canonical_anchor_window=True,
        )
        results=[]
        for candidate in expanded:
            result=candidate.model_dump(mode='json')
            result['artifact_id']=document_artifacts[candidate.document_id]
            results.append(result)
        return results, diagnostics.as_dict()
    @staticmethod
    def _terms(text): return list(dict.fromkeys(re.findall(r'[\wÀ-ỹ]+',text.casefold())))
    @staticmethod
    def _uuid(value):
        from uuid import UUID
        return UUID(value)
    def _result(self,v,rank,artifact_id):
        score,cid,r,ds,dr,ls,lr=v; return {
            'chunk_id':cid,'document_id':r[1],'artifact_id':artifact_id,'legal_unit_id':r[2],
            'content_text':r[3],'metadata_json':json.loads(r[4]),'provenance_json':json.loads(r[5]),
            'dense_score':ds,'dense_rank':dr,'lexical_score':ls,'lexical_rank':lr,'fusion_score':score,
            'retrieval_final_rank':rank,'final_rank':rank,'context_candidate_order':rank,
            'candidate_origin':'RETRIEVAL','hierarchy_relation':None,'hierarchy_depth':0,
            'anchor_chunk_id':None,'anchor_legal_unit_id':None,'anchor_retrieval_final_rank':None,
            'hierarchy_anchor_references':[],
        }
    def _queryable_ids(self):
        with self.catalog._connect() as c:return [r[0] for r in c.execute("SELECT document_id FROM local_documents WHERE preparation_state='INDEX_READY' ORDER BY document_id")]
    def _doc(self,id):
        with self.catalog._connect() as c:r=c.execute('SELECT document_id,preparation_state,active_artifact_id FROM local_documents WHERE document_id=?',(id,)).fetchone()
        if not r: raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_NOT_FOUND)
        return dict(zip(('document_id','preparation_state','active_artifact_id'),r))
    def _artifact(self,id):
        with self.catalog._connect() as c:r=c.execute('SELECT relative_path FROM local_artifacts WHERE artifact_id=?',(id,)).fetchone()
        if not r: raise LocalComputeError(LocalComputeErrorCode.CAPABILITY_UNAVAILABLE)
        return r[0]+'/artifact.sqlite3'
