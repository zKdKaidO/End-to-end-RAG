from app.context.schemas import ContextPackage, SelectedEvidence, StopReason
from app.retrieval.hierarchy_types import CandidateOrigin, HierarchyRelation
from app.retrieval.schemas import HierarchyAnchorReference
from evaluation.experiments.evidence_presentation_v1.presentation import (
    PRESENTATIONS,
    apply_presentation,
    normalized_lexemes,
    ordered_evidence,
)


class Counter:
    provider = "test"
    tokenizer_id = "test"

    def count(self, text: str) -> int:
        return len(text.split())


def selected(
    index: int,
    text: str,
    *,
    origin: CandidateOrigin = CandidateOrigin.RETRIEVAL,
    anchor: str | None = None,
) -> SelectedEvidence:
    chunk_id = f"00000000-0000-0000-0000-00000000000{index}"
    anchor_ref = (
        [HierarchyAnchorReference(
            anchor_chunk_id=anchor,
            anchor_legal_unit_id="10000000-0000-0000-0000-000000000001",
            anchor_retrieval_final_rank=1,
        )]
        if anchor else []
    )
    return SelectedEvidence(
        source_id=f"S{index}",
        chunk_id=chunk_id,
        document_id="20000000-0000-0000-0000-000000000001",
        content_text=text,
        metadata_json={"document_type": "Nghị định", "document_number": "1"},
        provenance_json={"page_start": index},
        retrieval_final_rank=index if origin == CandidateOrigin.RETRIEVAL else None,
        context_candidate_order=index,
        candidate_origin=origin,
        legal_unit_id=f"30000000-0000-0000-0000-00000000000{index}",
        hierarchy_relation=HierarchyRelation.DIRECT_CHILD if anchor else None,
        hierarchy_depth=1 if anchor else 0,
        anchor_chunk_id=anchor,
        anchor_legal_unit_id="10000000-0000-0000-0000-000000000001" if anchor else None,
        anchor_retrieval_final_rank=1 if anchor else None,
        hierarchy_anchor_references=anchor_ref,
        dense_score=0.9 if origin == CandidateOrigin.RETRIEVAL else None,
        dense_rank=index if origin == CandidateOrigin.RETRIEVAL else None,
        lexical_score=None,
        lexical_rank=None,
        fusion_score=0.01 if origin == CandidateOrigin.RETRIEVAL else None,
        token_count=10,
    )


def package() -> ContextPackage:
    anchor = selected(1, "quy định chung")
    other = selected(2, "thời hạn báo cáo")
    child = selected(3, "chi tiết trực tiếp", origin=CandidateOrigin.HIERARCHY_CHILD, anchor=anchor.chunk_id)
    return ContextPackage(
        request_id="test",
        query_text="Thời hạn báo cáo là bao lâu?",
        context_text="unused",
        selected_evidence=[anchor, other, child],
        context_token_count=1,
        context_budget_tokens=500,
        candidate_count=3,
        duplicate_count=0,
        selected_count=3,
        dropped_count=0,
        budget_exhausted=False,
        stop_reason=StopReason.NONE,
    )


def test_normalized_lexemes_are_unicode_safe_and_deduplicated():
    assert normalized_lexemes("Bảo hiểm, bảo hiểm: người lao động!") == (
        "bảo", "hiểm", "người", "lao", "động"
    )


def test_query_overlap_ordering_is_ground_truth_free_and_deterministic():
    ordered = ordered_evidence(package(), "query_overlap")
    assert ordered[0].content_text == "thời hạn báo cáo"
    assert {item.chunk_id for item in ordered} == {item.chunk_id for item in package().selected_evidence}


def test_anchor_child_order_keeps_child_immediately_after_anchor():
    ordered = ordered_evidence(package(), "anchor_children")
    assert ordered[1].candidate_origin == CandidateOrigin.HIERARCHY_CHILD
    assert ordered[1].anchor_chunk_id == ordered[0].chunk_id


def test_every_presentation_preserves_selected_set_and_reassigns_exact_source_ids():
    original = package()
    for spec in PRESENTATIONS.values():
        rendered = apply_presentation(original, spec, Counter())
        assert {item.chunk_id for item in rendered.selected_evidence} == {
            item.chunk_id for item in original.selected_evidence
        }
        assert [item.source_id for item in rendered.selected_evidence] == ["S1", "S2", "S3"]
        assert rendered.context_token_count <= rendered.context_budget_tokens


def test_group_wrapper_uses_only_stored_hierarchy_relationship():
    rendered = apply_presentation(package(), PRESENTATIONS["P1"], Counter())
    assert "[S3] CHILD_OF=S1" in rendered.context_text
    assert "expected" not in rendered.context_text.lower()
