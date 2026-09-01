from __future__ import annotations

import os
import uuid

import pytest

from app.generation.profile import get_generation_profile
from app.local_compute.documents import LocalDocumentStore
from app.local_compute.generation import (
    GenerationProviderType,
    GenerationRouter,
    LocalAnswerService,
    LocalGenerationProvider,
)
from app.local_compute.indexing import LocalIndexService
from app.local_compute.preparation import LocalPreparationService
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.settings import LocalComputeSettings

from tests.unit.local_compute.test_hierarchy_context import _pdf_bytes


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LOCAL_GENERATION_E2E") != "1",
    reason="set RUN_LOCAL_GENERATION_E2E=1 only when the configured local Ollama model is available",
)


@pytest.mark.asyncio
async def test_real_local_generation_e2e(tmp_path):
    settings = LocalComputeSettings(
        data_root=tmp_path / "Compute",
        development_mode=True,
        development_origins=("http://localhost:5173",),
        # Docker-only development bridge to the same host's local Ollama.
        local_generation_base_url="http://host.docker.internal:11434",
    )
    runtime = LocalComputeRuntime(settings)
    runtime.start()
    provider = LocalGenerationProvider(
        get_generation_profile(),
        settings.local_generation_base_url,
        development_mode=True,
    )
    document_id = str(uuid.uuid4())
    source = (
        "NGHỊ ĐỊNH\n"
        "Số: 01/2026\n"
        "Điều 1. Mức phí.\n"
        "1. Mức phí là 10 phần trăm.\n"
        "Điều 2. Quy định khác.\n"
        "1. Nội dung khác."
    )
    try:
        LocalDocumentStore(settings, runtime.catalog).accept_document(
            document_id, [_pdf_bytes(source)], "legal.pdf", "application/pdf"
        )
        LocalPreparationService(settings, runtime.catalog).prepare(document_id)
        LocalIndexService(settings, runtime.catalog).index_document(document_id)

        response = await LocalAnswerService(
            settings,
            runtime.catalog,
            GenerationRouter(provider),
        ).answer(
            request_id="real-local-generation-e2e",
            query_text="Mức phí là bao nhiêu?",
            document_ids=[document_id],
        )
        assert response.provider == GenerationProviderType.LOCAL
        assert response.model_id == "qwen3.5:9b"
        assert response.result.answer_text.strip()
        assert response.result.citations
        assert all(
            citation.source_id.startswith("S")
            and citation.document_id == document_id
            and citation.provenance_json["document_id"] == document_id
            for citation in response.result.citations
        )
        assert response.result.invalid_citations == []
        assert response.timings["generation_ms"] is not None
    finally:
        await provider.close()
        runtime.shutdown()
