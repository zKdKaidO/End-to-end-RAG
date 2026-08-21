from collections import defaultdict
from collections.abc import Sequence
from time import perf_counter
from uuid import UUID

from app.core.logging import get_logger
from app.retrieval.hierarchy_types import (
    CandidateOrigin,
    DirectChildRow,
    HierarchyExpansionDiagnostics,
    HierarchyExpansionStatus,
    HierarchyRelation,
)
from app.retrieval.schemas import HierarchyAnchorReference, RetrievedCandidate


logger = get_logger(__name__)


class LegalHierarchyExpander:
    """Bounded one-hop direct-child enrichment over immutable RRF anchors."""

    def __init__(
        self,
        repository,
        *,
        enabled: bool,
        max_anchors: int,
        max_children_per_anchor: int,
        max_candidates_added: int,
        depth: int,
    ):
        if max_anchors != 10 or max_children_per_anchor != 4:
            raise ValueError("Hierarchy V2 anchor and per-anchor bounds are frozen")
        if max_candidates_added != 20 or depth != 1:
            raise ValueError("Hierarchy V2 global bound and depth are frozen")
        self.repository = repository
        self.enabled = enabled
        self.max_anchors = max_anchors
        self.max_children_per_anchor = max_children_per_anchor
        self.max_candidates_added = max_candidates_added
        self.depth = depth

    def expand(
        self,
        base_candidates: Sequence[RetrievedCandidate],
        document_ids: Sequence[UUID],
        *,
        canonical_anchor_window: bool,
    ) -> tuple[list[RetrievedCandidate], HierarchyExpansionDiagnostics]:
        started = perf_counter()
        ordered = sorted(
            base_candidates,
            key=lambda item: (item.retrieval_final_rank or 10**9, item.chunk_id),
        )
        diagnostics = HierarchyExpansionDiagnostics(
            status=HierarchyExpansionStatus.NO_EXPANSION,
            enabled=self.enabled,
            stage="HIERARCHY_ANCHOR_SELECTION",
            base_anchor_count=len(ordered),
        )

        if not self.enabled or not canonical_anchor_window:
            diagnostics.status = HierarchyExpansionStatus.DISABLED
            diagnostics.reason_codes.append(
                "HIERARCHY_DISABLED" if not self.enabled else "NON_CANONICAL_BASE_WINDOW"
            )
            result = self._renumber_base(ordered)
            diagnostics.hierarchy_total_ms = (perf_counter() - started) * 1000
            return result, diagnostics

        anchors = ordered[: self.max_anchors]
        unit_groups: dict[str, list[RetrievedCandidate]] = {}
        for anchor in anchors:
            if anchor.legal_unit_id is None:
                diagnostics.anchors_without_legal_unit += 1
                self._reason(diagnostics, "NO_LEGAL_UNIT")
                continue
            unit_groups.setdefault(anchor.legal_unit_id, []).append(anchor)
        diagnostics.unique_anchor_unit_count = len(unit_groups)
        if diagnostics.unique_anchor_unit_count < (
            diagnostics.base_anchor_count - diagnostics.anchors_without_legal_unit
        ):
            self._reason(diagnostics, "DUPLICATE_ANCHOR_UNIT_COLLAPSED")

        if not unit_groups:
            diagnostics.reason_codes.append("NO_EXPANDABLE_ANCHOR")
            result = self._renumber_base(ordered)
            diagnostics.hierarchy_total_ms = (perf_counter() - started) * 1000
            return result, diagnostics

        primary_anchors = [group[0] for group in unit_groups.values()]
        primary_anchors.sort(key=lambda item: (item.retrieval_final_rank, item.chunk_id))
        group_by_primary = {
            group[0].chunk_id: group
            for group in unit_groups.values()
        }

        try:
            lookup_started = perf_counter()
            rows = self.repository.lookup_direct_children(
                [UUID(item.chunk_id) for item in primary_anchors],
                document_ids,
            )
            diagnostics.hierarchy_lookup_ms = (perf_counter() - lookup_started) * 1000
            diagnostics.stage = "HIERARCHY_LOOKUP"
            diagnostics.children_examined = len(rows)
            result = self._merge(
                ordered,
                rows,
                group_by_primary,
                document_ids,
                diagnostics,
            )
        except Exception as exc:
            diagnostics.status = HierarchyExpansionStatus.BASELINE_FALLBACK
            diagnostics.fallback_used = True
            diagnostics.reason_codes.append("HIERARCHY_LOOKUP_FAILED")
            diagnostics.stage = "HIERARCHY_LOOKUP"
            result = self._renumber_base(ordered)
            logger.warning(
                "hierarchy_baseline_fallback",
                stage=diagnostics.stage,
                error_type=type(exc).__name__,
                base_anchor_count=len(ordered),
            )

        diagnostics.hierarchy_total_ms = (perf_counter() - started) * 1000
        return result, diagnostics

    def _merge(
        self,
        ordered: list[RetrievedCandidate],
        rows: list[DirectChildRow],
        group_by_primary: dict[str, list[RetrievedCandidate]],
        document_ids: Sequence[UUID],
        diagnostics: HierarchyExpansionDiagnostics,
    ) -> list[RetrievedCandidate]:
        diagnostics.stage = "HIERARCHY_DEDUP"
        allowed_documents = {str(value) for value in document_ids}
        base_by_id = {item.chunk_id: item for item in ordered}
        rows_by_anchor: dict[str, list[DirectChildRow]] = defaultdict(list)
        anchor_by_id = {item.chunk_id: item for item in ordered}

        for row in rows:
            anchor_id = str(row.anchor_chunk_id)
            anchor = anchor_by_id.get(anchor_id)
            group = group_by_primary.get(anchor_id)
            if anchor is None or group is None:
                raise ValueError("Hierarchy lookup returned an unknown anchor")
            if str(row.anchor_legal_unit_id) != anchor.legal_unit_id:
                raise ValueError("Hierarchy lookup returned an invalid anchor relation")
            if row.child_legal_unit_id == row.anchor_legal_unit_id:
                raise ValueError("Hierarchy lookup returned a self-parent relation")
            if str(row.document_id) != anchor.document_id:
                raise ValueError("Hierarchy child document differs from its anchor")
            if allowed_documents and str(row.document_id) not in allowed_documents:
                diagnostics.document_filter_rejections += 1
                continue
            rows_by_anchor[anchor_id].append(row)

        eligible_by_anchor: dict[str, list[str]] = defaultdict(list)
        child_rows: dict[str, DirectChildRow] = {}
        child_references: dict[str, list[HierarchyAnchorReference]] = defaultdict(list)

        for primary_id, group in group_by_primary.items():
            raw_rows = rows_by_anchor.get(primary_id, [])
            if not raw_rows:
                diagnostics.anchors_without_children += 1
                continue
            seen_for_anchor: set[str] = set()
            for row in raw_rows:
                child_id = str(row.child_chunk_id)
                if child_id in seen_for_anchor:
                    diagnostics.duplicates_rejected += 1
                    continue
                seen_for_anchor.add(child_id)
                if child_id in base_by_id:
                    diagnostics.duplicates_rejected += 1
                    self._reason(diagnostics, "BASE_CANDIDATE_WINS")
                    continue
                eligible_by_anchor[primary_id].append(child_id)
                child_rows.setdefault(child_id, row)
                for anchor in group:
                    reference = HierarchyAnchorReference(
                        anchor_chunk_id=anchor.chunk_id,
                        anchor_legal_unit_id=anchor.legal_unit_id,
                        anchor_retrieval_final_rank=anchor.retrieval_final_rank,
                    )
                    if reference not in child_references[child_id]:
                        child_references[child_id].append(reference)

        for references in child_references.values():
            references.sort(
                key=lambda item: (
                    item.anchor_retrieval_final_rank,
                    item.anchor_chunk_id,
                )
            )

        diagnostics.stage = "HIERARCHY_ORDERING"
        output: list[RetrievedCandidate] = []
        emitted_children: set[str] = set()
        expanded_anchor_ids: set[str] = set()

        for anchor in ordered:
            output.append(anchor.model_copy(update={"context_candidate_order": len(output) + 1}))
            emitted_for_anchor = 0
            eligible_ids = eligible_by_anchor.get(anchor.chunk_id, [])
            for child_id in eligible_ids:
                if child_id in emitted_children:
                    diagnostics.duplicates_rejected += 1
                    self._reason(diagnostics, "MULTIPLE_ANCHOR_DISCOVERY")
                    continue
                if emitted_for_anchor >= self.max_children_per_anchor:
                    diagnostics.per_anchor_cap_hits += 1
                    self._reason(diagnostics, "PER_ANCHOR_CAP_REACHED")
                    break
                if diagnostics.children_added >= self.max_candidates_added:
                    diagnostics.global_cap_reached = True
                    self._reason(diagnostics, "GLOBAL_CAP_REACHED")
                    break
                row = child_rows[child_id]
                references = child_references[child_id]
                primary = references[0]
                output.append(
                    RetrievedCandidate(
                        chunk_id=child_id,
                        document_id=str(row.document_id),
                        content_text=row.content_text,
                        metadata_json=row.metadata_json,
                        provenance_json=row.provenance_json,
                        dense_score=None,
                        dense_rank=None,
                        lexical_score=None,
                        lexical_rank=None,
                        fusion_score=None,
                        retrieval_final_rank=None,
                        final_rank=None,
                        context_candidate_order=len(output) + 1,
                        candidate_origin=CandidateOrigin.HIERARCHY_CHILD,
                        legal_unit_id=str(row.child_legal_unit_id),
                        hierarchy_relation=HierarchyRelation.DIRECT_CHILD,
                        hierarchy_depth=1,
                        anchor_chunk_id=primary.anchor_chunk_id,
                        anchor_legal_unit_id=primary.anchor_legal_unit_id,
                        anchor_retrieval_final_rank=primary.anchor_retrieval_final_rank,
                        hierarchy_anchor_references=references,
                    )
                )
                emitted_children.add(child_id)
                emitted_for_anchor += 1
                diagnostics.children_added += 1
                expanded_anchor_ids.add(anchor.chunk_id)

        diagnostics.anchors_expanded = len(expanded_anchor_ids)
        diagnostics.status = (
            HierarchyExpansionStatus.EXPANDED
            if diagnostics.children_added
            else HierarchyExpansionStatus.NO_EXPANSION
        )
        if diagnostics.status == HierarchyExpansionStatus.NO_EXPANSION:
            self._reason(diagnostics, "NO_DIRECT_CHILD_CANDIDATE")
        return output

    @staticmethod
    def _renumber_base(ordered: list[RetrievedCandidate]) -> list[RetrievedCandidate]:
        return [
            item.model_copy(update={"context_candidate_order": index})
            for index, item in enumerate(ordered, start=1)
        ]

    @staticmethod
    def _reason(diagnostics: HierarchyExpansionDiagnostics, reason: str) -> None:
        if reason not in diagnostics.reason_codes:
            diagnostics.reason_codes.append(reason)
