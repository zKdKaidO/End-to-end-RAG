from uuid import UUID

from app.context.formatter import (
    MISSING_LEGAL_IDENTITY,
    format_evidence_block,
    format_legal_identity,
)
from app.retrieval.schemas import RetrievedCandidate


def candidate(metadata=None, content="Điều 5. Nội dung nguyên văn."):
    return RetrievedCandidate(
        chunk_id=str(UUID(int=1)),
        document_id=str(UUID(int=10)),
        content_text=content,
        metadata_json=metadata or {},
        provenance_json={"page_start": 7, "page_end": 8},
        dense_score=0.8,
        dense_rank=1,
        lexical_score=0.2,
        lexical_rank=2,
        fusion_score=0.03,
        final_rank=1,
    )


def test_formatter_renders_source_id_real_identity_and_content():
    item = candidate(
        {
            "document_type": "Nghị định",
            "document_number": "135/2026/NĐ-CP",
            "title": "Quy định cơ chế, chính sách ưu đãi",
        }
    )
    block = format_evidence_block(item, "S1")
    assert block.startswith("[Evidence S1]\n")
    assert "Nguồn: Nghị định số 135/2026/NĐ-CP — Quy định cơ chế, chính sách ưu đãi" in block
    assert block.endswith(item.content_text)


def test_formatter_does_not_render_machine_fields_or_dump_metadata():
    item = candidate(
        {
            "document_type": "Nghị định",
            "document_number": "135/2026/NĐ-CP",
            "title": "Tên văn bản",
            "issuing_authority": "Chính phủ",
            "issued_date": "2026-04-07",
            "internal_only": "secret-marker",
        }
    )
    block = format_evidence_block(item, "S1")
    assert item.chunk_id not in block
    assert item.document_id not in block
    assert "page_start" not in block
    assert "secret-marker" not in block
    assert "0.8" not in block
    assert "Chính phủ" not in block


def test_missing_metadata_is_explicit_without_fabricated_identity():
    block = format_evidence_block(candidate({}), "S2")
    assert f"Nguồn: {MISSING_LEGAL_IDENTITY}" in block
    assert "Luật" not in block
    assert "Nghị định" not in block


def test_partial_actual_metadata_is_used_without_inventing_fields():
    assert format_legal_identity({"title": "Tên thật"}) == "Tên thật"
    assert format_legal_identity({"document_number": "12/QĐ"}) == "Số 12/QĐ"
    assert format_legal_identity({"document_type": "Quyết định"}) == "Quyết định"


def test_content_text_is_preserved_exactly():
    content = "  Khoản 1.\nNội  dung không bị sửa.  "
    block = format_evidence_block(candidate({}, content), "S1")
    assert block.endswith(content)
