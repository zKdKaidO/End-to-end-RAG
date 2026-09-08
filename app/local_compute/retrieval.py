"""Local hybrid retrieval over the selected INDEX_READY artifact set.

Dense vectors share one E5 model and normalized-vector contract, so their
cosine scores are comparable across artifacts. FTS5 BM25 values, however,
are calculated using each artifact's local corpus statistics. We therefore
never treat raw BM25 values from different SQLite files as global scores.
Instead, each artifact contributes its ordered lexical stream and the streams
are deterministically interleaved by local rank, then by the within-artifact
relative BM25 signal, document id, and chunk id. This creates one unique,
global lexical rank without pretending cross-file BM25 is calibrated.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass

import numpy as np

from app.indexing.embedder import E5Embedder
from app.retrieval.hierarchy_expander import LegalHierarchyExpander
from app.retrieval.query_embedder import QueryEmbedder
from app.retrieval.schemas import RetrievedCandidate

from .answer_modes import answer_mode_profile
from .errors import LocalComputeError, LocalComputeErrorCode
from .hierarchy import LocalHierarchyRepository
from .legal_paths import LocalArtifactLegalPathResolver
from .reranker import LocalQwenReranker


@dataclass(frozen=True)
class _ArtifactRow:
    chunk_id: str
    document_id: str
    legal_unit_id: str | None
    content_text: str
    metadata_json: str
    provenance_json: str
    vector: bytes
    dimension: int
    normalized: int
    index_version: str
    legal_path: tuple[str, ...]
    legal_path_metadata: dict | None = None


@dataclass(frozen=True)
class _LexicalHit:
    chunk_id: str
    document_id: str
    bm25: float
    local_rank: int
    relative_score: float


class LocalRetrievalStore:
    TOP_DENSE = 50
    TOP_LEXICAL = 50
    TOP_FINAL = 10
    RRF_K = 60

    def __init__(self, settings, catalog):
        self.settings, self.catalog = settings, catalog
        self._reranker: LocalQwenReranker | None = None

    def query_document_set(
        self, query_text, document_ids=None, answer_mode=None, retrieval_queries=None
    ):
        results, _ = self.query_document_set_with_diagnostics(
            query_text, document_ids, answer_mode, retrieval_queries
        )
        return results

    def query_document_set_with_diagnostics(
        self, query_text, document_ids=None, answer_mode=None, retrieval_queries=None
    ):
        if not isinstance(query_text, str) or not query_text.strip():
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST)
        profile = answer_mode_profile(answer_mode)
        try:
            embedder = E5Embedder.get_instance(
                cache_dir=str(self.settings.embedding_model_cache_dir), device="cpu"
            )
            query_terms = self._normalized_queries(query_text, retrieval_queries)
            query_vectors = [QueryEmbedder(embedder).encode(item) for item in query_terms]
        except Exception as exc:
            raise LocalComputeError(
                LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE
            ) from exc

        requested = document_ids or self._queryable_ids()
        document_artifacts: dict[str, str] = {}
        resolvers_by_document: dict[str, LocalArtifactLegalPathResolver] = {}
        rows_by_chunk: dict[str, _ArtifactRow] = {}
        all_rows: list[_ArtifactRow] = []
        lexical_streams: list[list[list[_LexicalHit]]] = [
            [] for _ in query_terms
        ]

        # First load every eligible artifact. No branch rank is assigned while
        # iterating a document: both branches receive their ranks only after
        # their complete selected-document pool is known.
        for document_id in requested:
            document = self._doc(document_id)
            if document["preparation_state"] != "INDEX_READY":
                raise LocalComputeError(
                    LocalComputeErrorCode.CAPABILITY_UNAVAILABLE,
                    "Document is not locally queryable.",
                )
            artifact_id = document["active_artifact_id"]
            document_artifacts[document_id] = artifact_id
            with sqlite3.connect(
                self.settings.data_root / self._artifact(artifact_id)
            ) as db:
                resolver = LocalArtifactLegalPathResolver(db)
                resolvers_by_document[document_id] = resolver
                artifact_rows = self._load_rows(db, resolver)
                by_chunk = {row.chunk_id: row for row in artifact_rows}
                rows_by_chunk.update(by_chunk)
                all_rows.extend(artifact_rows)
                for query_index, retrieval_query in enumerate(query_terms):
                    terms = self._terms(retrieval_query)
                    if terms:
                        lexical_streams[query_index].append(
                            self._lexical_stream(
                                db, by_chunk, document_id, terms, profile.top_lexical
                            )
                        )

        dense_ranks: dict[str, tuple[float, int]] = {}
        coverage_anchor_ids: list[str] = []
        for query_vector in query_vectors:
            ranked = self._global_dense_ranks(
                [(float(np.dot(query_vector, self._valid_vector(row))), row) for row in all_rows],
                profile.top_dense,
            )
            if ranked:
                coverage_anchor_ids.append(next(iter(ranked)))
            dense_ranks = self._merge_branch_ranks(dense_ranks, ranked)
        lexical_ranks: dict[str, int] = {}
        lexical_scores: dict[str, float] = {}
        for streams in lexical_streams:
            ranks, scores = self._global_lexical_ranks(streams)
            if ranks:
                coverage_anchor_ids.append(next(iter(ranks)))
            merged_lexical = self._merge_branch_ranks(
                {chunk_id: (lexical_scores[chunk_id], rank) for chunk_id, rank in lexical_ranks.items()},
                {chunk_id: (scores[chunk_id], rank) for chunk_id, rank in ranks.items()},
            )
            lexical_ranks = {chunk_id: rank for chunk_id, (_score, rank) in merged_lexical.items()}
            lexical_scores = {chunk_id: score for chunk_id, (score, _rank) in merged_lexical.items()}
        merged_ids = set(dense_ranks) | set(lexical_ranks)
        fused: list[
            tuple[
                float,
                str,
                _ArtifactRow,
                float | None,
                int | None,
                float | None,
                int | None,
            ]
        ] = []
        for chunk_id in merged_ids:
            row = rows_by_chunk[chunk_id]
            dense_score, dense_rank = dense_ranks.get(chunk_id, (None, None))
            lexical_score, lexical_rank = (
                lexical_scores.get(chunk_id),
                lexical_ranks.get(chunk_id),
            )
            score = (
                profile.dense_rrf_weight / (self.RRF_K + dense_rank)
                if dense_rank is not None
                else 0.0
            ) + (
                profile.lexical_rrf_weight / (self.RRF_K + lexical_rank)
                if lexical_rank is not None
                else 0.0
            )
            fused.append(
                (score, chunk_id, row, dense_score, dense_rank, lexical_score, lexical_rank)
            )

        fused.sort(key=lambda item: (-item[0], item[1]))
        rerank_ms: float | None = None
        rerank_fallback = False
        if getattr(self.settings, "reranker_enabled", False):
            if self._reranker is None:
                self._reranker = LocalQwenReranker(
                    device=getattr(self.settings, "reranker_device", "cpu"),
                    max_candidates=getattr(self.settings, "reranker_max_candidates", 50),
                )
            reranked = self._reranker.rank(
                query_text,
                [(item[1], item[2].content_text) for item in fused],
            )
            rerank_ms, rerank_fallback = reranked.elapsed_ms, reranked.fallback_used
            by_id = {item[1]: item for item in fused}
            fused = [by_id[chunk_id] for chunk_id in reranked.ordered_ids if chunk_id in by_id]
        # Complex-query coverage anchors are selected before redundant global
        # winners. They remain genuine dense/lexical candidates and receive no
        # artificial RRF bonus; this only prevents one topic from consuming
        # the entire final context window.
        fused_by_id = {item[1]: item for item in fused}
        selected_fused: list[tuple] = []
        seen: set[str] = set()
        for chunk_id in coverage_anchor_ids:
            item = fused_by_id.get(chunk_id)
            if item is not None and chunk_id not in seen:
                selected_fused.append(item)
                seen.add(chunk_id)
            if len(selected_fused) == profile.top_final:
                break
        for item in fused:
            if item[1] not in seen:
                selected_fused.append(item)
                seen.add(item[1])
            if len(selected_fused) == profile.top_final:
                break
        base = [
            self._result(item, rank, document_artifacts[item[2].document_id])
            for rank, item in enumerate(selected_fused, start=1)
        ]
        candidates = [
            RetrievedCandidate.model_validate(
                {
                    key: value
                    for key, value in result.items()
                    if key in RetrievedCandidate.model_fields
                }
            )
            for result in base
        ]
        expander = LegalHierarchyExpander(
            LocalHierarchyRepository(self.settings, self.catalog, document_artifacts),
            enabled=True,
            max_anchors=profile.hierarchy_max_anchors,
            max_children_per_anchor=profile.hierarchy_children_per_anchor,
            max_candidates_added=20,
            depth=1,
        )
        expanded, diagnostics = expander.expand(
            candidates,
            [self._uuid(document_id) for document_id in requested],
            canonical_anchor_window=True,
        )
        results: list[dict] = []
        for candidate in expanded:
            resolver = resolvers_by_document.get(candidate.document_id)
            result = self._enrich_authoritative_path(candidate, resolver).model_dump(mode="json")
            result["artifact_id"] = document_artifacts[candidate.document_id]
            results.append(result)
        diagnostic_payload = diagnostics.as_dict()
        diagnostic_payload.update(
            {
                "answer_mode": profile.mode.value,
                "lexical_global_fusion": "DOCUMENT_BALANCED_RELATIVE_BM25",
                "global_dense_candidate_count": len(all_rows),
                "global_lexical_candidate_count": len(lexical_ranks),
                "retrieval_query_count": len(query_terms),
                "coverage_anchor_chunk_ids": [
                    chunk_id for chunk_id in coverage_anchor_ids if chunk_id in fused_by_id
                ],
                "rerank_ms": rerank_ms,
                "rerank_fallback_used": rerank_fallback,
                "retrieval_profile": {
                    "top_dense": profile.top_dense,
                    "top_lexical": profile.top_lexical,
                    "top_final": profile.top_final,
                    "dense_rrf_weight": profile.dense_rrf_weight,
                    "lexical_rrf_weight": profile.lexical_rrf_weight,
                    "context_budget_tokens": profile.context_budget_tokens,
                },
            }
        )
        return results, diagnostic_payload

    @staticmethod
    def _load_rows(
        db: sqlite3.Connection, resolver: LocalArtifactLegalPathResolver
    ) -> list[_ArtifactRow]:
        output: list[_ArtifactRow] = []
        for row in db.execute(
                """
                SELECT c.id, c.document_id, c.legal_unit_id, c.content_text,
                       c.metadata_json, c.provenance_json, e.vector,
                       e.dimension, e.normalized, e.index_version
                FROM chunks AS c
                JOIN chunk_embeddings AS e ON e.chunk_id = c.id
                """
            ):
            provenance = json.loads(row[5])
            resolved = resolver.resolve_for_span(
                row[2], provenance.get("char_start"), provenance.get("char_end")
            )
            output.append(_ArtifactRow(
                *row,
                (resolved.labels if resolved else ()),
                (resolved.as_metadata() if resolved else None),
            ))
        return output

    @staticmethod
    def _enrich_authoritative_path(candidate, resolver: LocalArtifactLegalPathResolver | None):
        if resolver is None:
            return candidate
        provenance = candidate.provenance_json
        path = resolver.resolve_for_span(
            candidate.legal_unit_id,
            provenance.get("char_start"),
            provenance.get("char_end"),
        )
        if path is None:
            return candidate
        metadata = dict(candidate.metadata_json)
        metadata["authoritative_legal_path"] = path.as_metadata()
        # Compatibility key for older formatter consumers. Its value is now
        # computed from the legal-unit repository, never read from metadata.
        if path.labels:
            metadata["legal_hierarchy_path"] = list(path.labels)
            metadata["legal_hierarchy_unit"] = path.labels[-1]
        else:
            metadata.pop("legal_hierarchy_path", None)
            metadata.pop("legal_hierarchy_unit", None)
        return candidate.model_copy(update={"metadata_json": metadata})

    @staticmethod
    def _valid_vector(row: _ArtifactRow) -> np.ndarray:
        vector = np.frombuffer(row.vector, dtype=np.float32)
        if (
            row.dimension != 768
            or row.normalized != 1
            or row.index_version != "block3-v1"
            or len(row.vector) != 3072
            or not np.isfinite(vector).all()
            or not math.isclose(float(np.linalg.norm(vector)), 1, abs_tol=1e-4)
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR, "Invalid local vector."
            )
        return vector

    @staticmethod
    def _global_dense_ranks(
        pool: list[tuple[float, _ArtifactRow]], limit: int
    ) -> dict[str, tuple[float, int]]:
        pool.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return {
            row.chunk_id: (score, rank)
            for rank, (score, row) in enumerate(pool[:limit], start=1)
        }

    @staticmethod
    def _merge_branch_ranks(
        existing: dict[str, tuple[float, int]], incoming: dict[str, tuple[float, int]]
    ) -> dict[str, tuple[float, int]]:
        """Retain one best branch signal per chunk across bounded subqueries."""
        merged = dict(existing)
        for chunk_id, (score, rank) in incoming.items():
            current = merged.get(chunk_id)
            if current is None or (rank, -score, chunk_id) < (current[1], -current[0], chunk_id):
                merged[chunk_id] = (score, rank)
        return merged

    @staticmethod
    def _lexical_stream(
        db: sqlite3.Connection,
        rows_by_chunk: dict[str, _ArtifactRow],
        document_id: str,
        terms: list[str],
        limit: int,
    ) -> list[_LexicalHit]:
        match = " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms)
        raw = list(
            db.execute(
                """
                SELECT chunk_id, bm25(chunk_fts)
                FROM chunk_fts
                WHERE chunk_fts MATCH ?
                ORDER BY bm25(chunk_fts), chunk_id
                LIMIT ?
                """,
                (match, limit),
            )
        )
        if not raw:
            return []
        # FTS5 lower BM25 is better. A per-artifact relative signal is used
        # only to break equal local-rank waves; it is never exposed as a
        # cross-artifact calibrated score.
        best = max(abs(float(bm25)) for _, bm25 in raw) or 1.0
        return [
            _LexicalHit(
                chunk_id=chunk_id,
                document_id=document_id,
                bm25=float(bm25),
                local_rank=rank,
                relative_score=abs(float(bm25)) / best,
            )
            for rank, (chunk_id, bm25) in enumerate(raw, start=1)
            if chunk_id in rows_by_chunk
        ]

    @staticmethod
    def _global_lexical_ranks(
        streams: list[list[_LexicalHit]],
    ) -> tuple[dict[str, int], dict[str, float]]:
        # One row from every artifact is considered before the next local-rank
        # wave. Thus an artifact-local rank=1 can no longer receive the same
        # global rank as every other artifact-local rank=1.
        hits = [hit for stream in streams for hit in stream]
        hits.sort(
            key=lambda hit: (
                hit.local_rank,
                -hit.relative_score,
                hit.document_id,
                hit.chunk_id,
            )
        )
        ranks: dict[str, int] = {}
        scores: dict[str, float] = {}
        for rank, hit in enumerate(hits, start=1):
            ranks.setdefault(hit.chunk_id, rank)
            scores.setdefault(hit.chunk_id, hit.relative_score)
        return ranks, scores

    @staticmethod
    def _terms(text: str) -> list[str]:
        # NFC makes Vietnamese combining forms stable. Numeric identifiers
        # survive intact; generic-term filtering deliberately stays out of the
        # core retriever until a measured corpus evaluation proves a safe list.
        import unicodedata

        return list(
            dict.fromkeys(
                re.findall(
                    r"[\wÀ-ỹ]+", unicodedata.normalize("NFC", text).casefold()
                )
            )
        )

    @staticmethod
    def _normalized_queries(query_text: str, retrieval_queries) -> tuple[str, ...]:
        if retrieval_queries is None:
            return (query_text,)
        if isinstance(retrieval_queries, (str, bytes)):
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST)
        values = [query_text]
        for value in retrieval_queries:
            if not isinstance(value, str) or not value.strip():
                raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST)
            if value.strip() not in values:
                values.append(value.strip())
        # The original query is mandatory and total retrieval work stays
        # bounded even if a future caller bypasses QueryPlan validation.
        return tuple(values[:4])

    @staticmethod
    def _uuid(value):
        from uuid import UUID

        return UUID(value)

    @staticmethod
    def _result(value, rank, artifact_id):
        score, chunk_id, row, dense_score, dense_rank, lexical_score, lexical_rank = value
        metadata = json.loads(row.metadata_json)
        if row.legal_path_metadata is not None:
            # Ephemeral retrieval enrichment sourced only from the active
            # artifact's legal_units table. It is not persisted or inferred.
            metadata = {
                **metadata,
                "authoritative_legal_path": row.legal_path_metadata,
            }
            if row.legal_path:
                metadata["legal_hierarchy_path"] = list(row.legal_path)
                metadata["legal_hierarchy_unit"] = row.legal_path[-1]
        return {
            "chunk_id": chunk_id,
            "document_id": row.document_id,
            "artifact_id": artifact_id,
            "legal_unit_id": row.legal_unit_id,
            "content_text": row.content_text,
            "metadata_json": metadata,
            "provenance_json": json.loads(row.provenance_json),
            "dense_score": dense_score,
            "dense_rank": dense_rank,
            "lexical_score": lexical_score,
            "lexical_rank": lexical_rank,
            "fusion_score": score,
            "retrieval_final_rank": rank,
            "final_rank": rank,
            "context_candidate_order": rank,
            "candidate_origin": "RETRIEVAL",
            "hierarchy_relation": None,
            "hierarchy_depth": 0,
            "anchor_chunk_id": None,
            "anchor_legal_unit_id": None,
            "anchor_retrieval_final_rank": None,
            "hierarchy_anchor_references": [],
        }

    def _queryable_ids(self):
        with self.catalog._connect() as connection:
            return [
                row[0]
                for row in connection.execute(
                    """
                    SELECT document_id FROM local_documents
                    WHERE preparation_state='INDEX_READY'
                    ORDER BY document_id
                    """
                )
            ]

    def _doc(self, document_id):
        with self.catalog._connect() as connection:
            row = connection.execute(
                """
                SELECT document_id, preparation_state, active_artifact_id
                FROM local_documents WHERE document_id=?
                """,
                (document_id,),
            ).fetchone()
        if not row:
            raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_NOT_FOUND)
        return dict(zip(("document_id", "preparation_state", "active_artifact_id"), row))

    def _artifact(self, artifact_id):
        with self.catalog._connect() as connection:
            row = connection.execute(
                "SELECT relative_path FROM local_artifacts WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        if not row:
            raise LocalComputeError(LocalComputeErrorCode.CAPABILITY_UNAVAILABLE)
        return row[0] + "/artifact.sqlite3"
