from __future__ import annotations

import pytest

from app.context.schemas import ContextPackage, SelectedEvidence, StopReason
from app.local_compute.structured_claims import StructuredClaimError, render_provider_text


ARTICLE_11 = "00000000-0000-0000-0000-000000000011"
ARTICLE_12 = "00000000-0000-0000-0000-000000000012"
CLAUSE_11 = "00000000-0000-0000-0000-000000000111"
CLAUSE_12 = "00000000-0000-0000-0000-000000000112"


def _path(unit_id: str, category_id: str, ancestors: list[str], labels: list[str]) -> dict:
    return {
        "legal_unit_id": unit_id,
        "unit_type": "CLAUSE",
        "display_label": labels[-1],
        "ancestor_unit_ids": ancestors,
        "ancestor_display_labels": labels,
        "category_root_id": category_id,
        "category_key": "K1" if category_id == ARTICLE_11 else "K2",
        "path_source": "LEGAL_UNIT_REPOSITORY",
    }


def _package() -> ContextPackage:
    evidence = [
        SelectedEvidence(
            source_id="S1", chunk_id="00000000-0000-0000-0000-000000000001",
            document_id="00000000-0000-0000-0000-000000000010", content_text="Hoạt động nghiên cứu.",
            metadata_json={"authoritative_legal_path": _path(CLAUSE_11, ARTICLE_11, [ARTICLE_11, CLAUSE_11], ["Điều 11 — Nghiên cứu", "Khoản 1"])},
            provenance_json={}, retrieval_final_rank=1, context_candidate_order=1,
            dense_score=0.9, dense_rank=1, lexical_score=None, lexical_rank=None, fusion_score=0.1, token_count=1,
        ),
        SelectedEvidence(
            source_id="S2", chunk_id="00000000-0000-0000-0000-000000000002",
            document_id="00000000-0000-0000-0000-000000000010", content_text="Hướng dẫn luận văn.",
            metadata_json={"authoritative_legal_path": _path(CLAUSE_12, ARTICLE_12, [ARTICLE_12, CLAUSE_12], ["Điều 12 — Tự cập nhật", "Khoản 1"])},
            provenance_json={}, retrieval_final_rank=2, context_candidate_order=2,
            dense_score=0.8, dense_rank=2, lexical_score=None, lexical_rank=None, fusion_score=0.09, token_count=1,
        ),
    ]
    return ContextPackage(request_id="r", query_text="q", context_text="x", selected_evidence=evidence,
        context_token_count=1, context_budget_tokens=2, candidate_count=2, duplicate_count=0,
        selected_count=2, dropped_count=0, budget_exhausted=False, stop_reason=StopReason.NONE)


def test_category_claim_is_rendered_from_authoritative_category_id():
    raw = '''{"answerability":"ANSWERABLE","claims":[{"claim_id":"C1","claim_text":"Nghiên cứu khoa học","supporting_source_ids":["S1"],"legal_category_key":"K1","claim_type":"CATEGORY_MEMBERSHIP"}]}'''
    output = render_provider_text(raw, _package())
    assert "Nghiên cứu khoa học — thuộc Điều 11 — Nghiên cứu [S1]" in output


def test_unknown_source_and_unknown_category_fail_closed():
    bad_source = '''{"answerability":"ANSWERABLE","claims":[{"claim_id":"C1","claim_text":"x","supporting_source_ids":["S9"],"legal_category_key":"K1","claim_type":"CATEGORY_MEMBERSHIP"}]}'''
    bad_category = '''{"answerability":"ANSWERABLE","claims":[{"claim_id":"C1","claim_text":"x","supporting_source_ids":["S1"],"legal_category_key":"K99","claim_type":"CATEGORY_MEMBERSHIP"}]}'''
    with pytest.raises(StructuredClaimError):
        render_provider_text(bad_source, _package())
    with pytest.raises(StructuredClaimError):
        render_provider_text(bad_category, _package())


def test_source_cannot_be_associated_to_a_neighbor_category():
    raw = '''{"answerability":"ANSWERABLE","claims":[{"claim_id":"C1","claim_text":"x","supporting_source_ids":["S1"],"legal_category_key":"K2","claim_type":"CATEGORY_MEMBERSHIP"}]}'''
    with pytest.raises(StructuredClaimError):
        render_provider_text(raw, _package())


def test_insufficient_evidence_has_no_claims():
    assert render_provider_text('{"answerability":"INSUFFICIENT_EVIDENCE","claims":[]}', _package()) == "[STATUS: INSUFFICIENT_EVIDENCE]"
