from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest

from app.core.config import settings as server_settings

from app.context.schemas import StopReason
from app.context.service import ContextBuilderService
from app.generation.profile import get_generation_profile
from app.generation.tokenizers import ContextTokenCounter
from app.local_compute.context_adapter import build_local_context
from app.local_compute.documents import LocalDocumentStore
from app.local_compute.errors import LocalComputeError
from app.local_compute.hierarchy import LocalHierarchyRepository
from app.local_compute.indexing import LocalIndexService
from app.local_compute.preparation import LocalPreparationService
from app.local_compute.retrieval import LocalRetrievalStore
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.settings import LocalComputeSettings


def _pdf_bytes(text: str) -> bytes:
    """Make a text-native Unicode PDF without relying on an image font.

    The minimal API image deliberately has no system font package.  A custom
    ToUnicode map lets PyMuPDF recover Vietnamese text through the normal PDF
    extraction path, while the visual glyph program remains irrelevant to this
    parser/integration fixture.
    """

    characters = sorted(set(text.replace("\n", "")))
    assert len(characters) <= 223
    code_by_character = {character: number for number, character in enumerate(characters, 32)}
    cmap = "\n".join(
        [
            "/CIDInit /ProcSet findresource begin",
            "12 dict begin",
            "begincmap",
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
            "/CMapName /ZKDUnicode def",
            "/CMapType 2 def",
            "1 begincodespacerange",
            "<20> <FE>",
            "endcodespacerange",
            f"{len(code_by_character)} beginbfchar",
            *[
                f"<{code:02X}> <{ord(character):04X}>"
                for character, code in code_by_character.items()
            ],
            "endbfchar",
            "endcmap",
            "CMapName currentdict /CMap defineresource pop",
            "end",
            "end",
        ]
    ).encode("ascii")
    content = b"BT /F1 11 Tf 72 1800 Td\n" + b"\n".join(
        f"<{''.join(f'{code_by_character[character]:02X}' for character in line)}> Tj 0 -14 Td".encode("ascii")
        for line in text.splitlines()
    ) + b"\nET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 2000] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(cmap), cmap),
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, value in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(value)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


@pytest.fixture
def runtime(tmp_path):
    instance = LocalComputeRuntime(
        LocalComputeSettings(
            data_root=tmp_path / "Compute",
            development_mode=True,
            development_origins=("http://localhost:5173",),
            embedding_model_cache_dir=Path(server_settings.EMBEDDING_MODEL_CACHE_DIR),
        )
    )
    instance.start()
    yield instance
    instance.shutdown()


def _prepare(runtime: LocalComputeRuntime, text: str, *, indexed: bool) -> tuple[str, str]:
    document_id = str(uuid.uuid4())
    LocalDocumentStore(runtime.settings, runtime.catalog).accept_document(
        document_id,
        [_pdf_bytes(text)],
        "hierarchy.pdf",
        "application/pdf",
    )
    prepared = LocalPreparationService(runtime.settings, runtime.catalog).prepare(document_id)
    if indexed:
        LocalIndexService(runtime.settings, runtime.catalog).index_document(document_id)
    return document_id, prepared["artifact_id"]


def _hierarchy_fixture() -> str:
    low_similarity_children = "\n".join(
        f"{number}. Quy tắc quasar basalt zircon riêng biệt {number}."
        for number in range(1, 5)
    )
    high_similarity_children = "\n".join(
        f"{number}. Doanh nghiệp thực hiện nghĩa vụ báo cáo theo hướng dẫn {number}."
        for number in range(5, 36)
    )
    return (
        "NGHỊ ĐỊNH\n"
        "Số: 01/2026\n"
        "Điều 1. Khung nghĩa vụ doanh nghiệp.\n"
        f"{low_similarity_children}\n"
        f"{high_similarity_children}\n"
        "Điều 2. Quy định độc lập.\n"
        "1. Nội dung của điều độc lập."
    )


def test_real_local_e5_hierarchy_and_block5_compatibility(runtime):
    document_id, artifact_id = _prepare(runtime, _hierarchy_fixture(), indexed=True)
    store = LocalRetrievalStore(runtime.settings, runtime.catalog)

    results, diagnostics = store.query_document_set_with_diagnostics(
        "khung nghĩa vụ doanh nghiệp", [document_id]
    )
    repeated, repeated_diagnostics = store.query_document_set_with_diagnostics(
        "khung nghĩa vụ doanh nghiệp", [document_id]
    )

    assert diagnostics["status"] == "EXPANDED"
    assert diagnostics["children_added"] > 0
    assert diagnostics["children_added"] <= 20
    assert diagnostics["hierarchy_total_ms"] >= 0
    assert repeated_diagnostics["status"] == "EXPANDED"
    assert results == repeated
    assert all(item["document_id"] == document_id for item in results)
    assert all(item["artifact_id"] == artifact_id for item in results)
    assert [item["context_candidate_order"] for item in results] == list(
        range(1, len(results) + 1)
    )

    children = [item for item in results if item["candidate_origin"] == "HIERARCHY_CHILD"]
    assert children
    assert all(item["hierarchy_relation"] == "DIRECT_CHILD" for item in children)
    assert all(item["hierarchy_depth"] == 1 for item in children)
    assert all(item["retrieval_final_rank"] is None for item in children)
    assert all(item["dense_rank"] is None for item in children)
    assert all(item["provenance_json"]["document_id"] == document_id for item in children)

    profile = get_generation_profile()
    counter = ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id)
    builder = ContextBuilderService(counter)
    package = build_local_context(
        request_id="local-hierarchy-context",
        query_text="khung nghĩa vụ doanh nghiệp",
        local_results=results,
        context_budget_tokens=profile.context_budget_tokens,
        context_builder=builder,
    )
    repeated_package = build_local_context(
        request_id="local-hierarchy-context",
        query_text="khung nghĩa vụ doanh nghiệp",
        local_results=repeated,
        context_budget_tokens=profile.context_budget_tokens,
        context_builder=builder,
    )
    assert package.context_text
    assert package.model_dump() == repeated_package.model_dump()
    assert package.context_token_count <= profile.context_budget_tokens
    assert [item.source_id for item in package.selected_evidence] == [
        f"S{index}" for index in range(1, package.selected_count + 1)
    ]
    assert [item.context_candidate_order for item in package.selected_evidence] == sorted(
        item.context_candidate_order for item in package.selected_evidence
    )
    assert any(item.candidate_origin.value == "HIERARCHY_CHILD" for item in package.selected_evidence)
    assert all(item.provenance_json["document_id"] == document_id for item in package.selected_evidence)

    top_evidence_tokens = package.selected_evidence[0].token_count
    assert top_evidence_tokens > 1
    budget_limited = build_local_context(
        request_id="local-hierarchy-budget",
        query_text="khung nghĩa vụ doanh nghiệp",
        local_results=results,
        context_budget_tokens=top_evidence_tokens - 1,
        context_builder=builder,
    )
    assert budget_limited.selected_count == 0
    assert budget_limited.budget_exhausted is True
    assert budget_limited.stop_reason == StopReason.TOP_EVIDENCE_EXCEEDS_CONTEXT_BUDGET


def test_local_hierarchy_repository_is_direct_child_and_artifact_isolated(runtime):
    source = (
        "Điều 1. Điều cha.\n"
        "1. Khoản một của điều cha.\n"
        "2. Khoản hai của điều cha.\n"
        "Điều 2. Điều anh chị em.\n"
        "1. Khoản một của điều anh chị em.\n"
        "Điều 3. Điều không có khoản."
    )
    document_id, artifact_id = _prepare(runtime, source, indexed=False)
    other_document_id, other_artifact_id = _prepare(
        runtime,
        "Điều 9. Văn bản khác.\n1. Khoản khác.",
        indexed=False,
    )
    artifact_path = runtime.settings.artifacts_path / document_id / artifact_id / "artifact.sqlite3"
    with sqlite3.connect(artifact_path) as db:
        anchor_id, anchor_unit = db.execute(
            """
            SELECT c.id, c.legal_unit_id
            FROM chunks AS c
            JOIN legal_units AS u ON u.id = c.legal_unit_id
            WHERE u.unit_type = 'ARTICLE' AND u.unit_number = '1'
            """
        ).fetchone()
        expected_direct_child_ids = {
            row[0]
            for row in db.execute(
                "SELECT id FROM legal_units WHERE parent_id = ?", (anchor_unit,))
            }
        leaf_anchor_id = db.execute(
            """
            SELECT c.id
            FROM chunks AS c
            JOIN legal_units AS u ON u.id = c.legal_unit_id
            WHERE u.unit_type = 'ARTICLE' AND u.unit_number = '3'
            """
        ).fetchone()[0]

    repository = LocalHierarchyRepository(
        runtime.settings,
        runtime.catalog,
        {document_id: artifact_id, other_document_id: other_artifact_id},
    )
    rows = repository.lookup_direct_children([uuid.UUID(anchor_id)], [uuid.UUID(document_id)])
    assert rows
    assert {str(row.child_legal_unit_id) for row in rows} <= expected_direct_child_ids
    assert all(str(row.document_id) == document_id for row in rows)
    assert all(row.child_unit_title != "Điều anh chị em" for row in rows)
    assert repository.lookup_direct_children(
        [uuid.UUID(leaf_anchor_id)], [uuid.UUID(document_id)]
    ) == []

    mismatched_repository = LocalHierarchyRepository(
        runtime.settings,
        runtime.catalog,
        {document_id: other_artifact_id},
    )
    with pytest.raises(LocalComputeError):
        mismatched_repository.lookup_direct_children([uuid.UUID(anchor_id)], [uuid.UUID(document_id)])
