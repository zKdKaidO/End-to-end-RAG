from __future__ import annotations

import pytest

from app.context.schemas import ContextPackage, SelectedEvidence, StopReason
from app.local_compute.grounded_output import GroundedOutputError, render_provider_text


def _package() -> ContextPackage:
    evidence = [
        SelectedEvidence(
            source_id="S1", chunk_id="00000000-0000-0000-0000-000000000001",
            document_id="00000000-0000-0000-0000-000000000010", content_text="Hướng dẫn chính: 25 giờ.",
            metadata_json={}, provenance_json={}, retrieval_final_rank=1, context_candidate_order=1,
            dense_score=0.9, dense_rank=1, lexical_score=None, lexical_rank=None, fusion_score=0.1, token_count=1,
        ),
        SelectedEvidence(
            source_id="S2", chunk_id="00000000-0000-0000-0000-000000000002",
            document_id="00000000-0000-0000-0000-000000000010", content_text="Đồng hướng dẫn được tính 75%.",
            metadata_json={}, provenance_json={}, retrieval_final_rank=2, context_candidate_order=2,
            dense_score=0.8, dense_rank=2, lexical_score=None, lexical_rank=None, fusion_score=0.09, token_count=1,
        ),
    ]
    return ContextPackage(request_id="r", query_text="q", context_text="x", selected_evidence=evidence,
        context_token_count=1, context_budget_tokens=2, candidate_count=2, duplicate_count=0,
        selected_count=2, dropped_count=0, budget_exhausted=False, stop_reason=StopReason.NONE)


def test_structured_calculation_uses_decimal_and_preserves_sources():
    raw = '''{"answerability":"ANSWERABLE","claims":[{"claim_text":"Kết quả là {{C1}} giờ.","supporting_source_ids":["S1","S2"],"direct_or_derived":"DERIVED","calculation_ids":["C1"]}],"calculations":[{"calculation_id":"C1","operation":"multiply","operands":[{"value":"25","source_id":"S1"},{"value":"0.75","source_id":"S2"}]}],"public_answer":""}'''
    rendered = render_provider_text(raw, _package())
    assert "Kết quả là 18.75 giờ. [S1] [S2]" in rendered
    assert "Tính C1: 18.75 [S1] [S2]" in rendered


def test_structured_calculation_rejects_unavailable_source():
    raw = '''{"answerability":"ANSWERABLE","claims":[{"claim_text":"x","supporting_source_ids":["S9"],"direct_or_derived":"DIRECT","calculation_ids":[]}],"calculations":[],"public_answer":""}'''
    with pytest.raises(GroundedOutputError):
        render_provider_text(raw, _package())
