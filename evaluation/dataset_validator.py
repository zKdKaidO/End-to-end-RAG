import json
import re
import unicodedata
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from evaluation.schemas import EvaluationDataset


_SPACE = re.compile(r"\s+")


class DatasetValidationError(ValueError):
    pass


def _normalize(value: str) -> str:
    return _SPACE.sub(" ", unicodedata.normalize("NFC", value)).strip()


def load_dataset(path: str | Path) -> EvaluationDataset:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return EvaluationDataset.model_validate(raw)
    except Exception as exc:
        raise DatasetValidationError(f"Invalid evaluation dataset: {exc}") from exc


def validate_dataset(dataset: EvaluationDataset, db) -> dict:
    case_ids = [case.case_id for case in dataset.cases]
    if len(case_ids) != len(set(case_ids)):
        raise DatasetValidationError("case_id values must be unique")

    declared_document_ids: set[UUID] = set()
    declared_chunk_ids: set[UUID] = set()
    for case in dataset.cases:
        try:
            declared_document_ids.update(UUID(value) for value in (case.document_ids or []))
            declared_document_ids.update(UUID(value) for value in case.expected_document_ids)
            declared_chunk_ids.update(
                UUID(value) for solution in case.acceptable_evidence_sets for value in solution
            )
        except ValueError as exc:
            raise DatasetValidationError(f"{case.case_id}: invalid UUID") from exc

    document_rows = db.execute(
        text("SELECT id FROM documents WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": [str(value) for value in declared_document_ids] or [str(UUID(int=0))]},
    ).scalars().all()
    missing_documents = declared_document_ids - set(document_rows)
    if missing_documents:
        raise DatasetValidationError(f"Missing documents: {sorted(map(str, missing_documents))}")

    chunk_rows = db.execute(
        text(
            """
            SELECT c.id, c.document_id, c.content_text, c.provenance_json,
                   EXISTS (
                       SELECT 1 FROM chunk_indexes ci
                       WHERE ci.chunk_id = c.id AND ci.index_version = 'block3-v1'
                   ) AS indexed
            FROM chunks c
            WHERE c.id = ANY(CAST(:ids AS uuid[]))
            """
        ),
        {"ids": [str(value) for value in declared_chunk_ids] or [str(UUID(int=0))]},
    ).mappings().all()
    chunks = {row["id"]: row for row in chunk_rows}
    missing_chunks = declared_chunk_ids - set(chunks)
    if missing_chunks:
        raise DatasetValidationError(f"Missing chunks: {sorted(map(str, missing_chunks))}")

    for case in dataset.cases:
        if not case.answerable:
            continue
        expected_docs = {UUID(value) for value in case.expected_document_ids}
        case_chunks = [
            chunks[UUID(value)] for solution in case.acceptable_evidence_sets for value in solution
        ]
        if any(not row["indexed"] for row in case_chunks):
            raise DatasetValidationError(f"{case.case_id}: expected chunk is not in block3-v1")
        if any(row["document_id"] not in expected_docs for row in case_chunks):
            raise DatasetValidationError(f"{case.case_id}: chunk/document mismatch")
        if any(not row["content_text"].strip() or not row["provenance_json"] for row in case_chunks):
            raise DatasetValidationError(f"{case.case_id}: missing content or provenance")
        reference = _normalize(case.source_reference or "")
        if not any(reference in _normalize(row["content_text"]) for row in case_chunks):
            raise DatasetValidationError(
                f"{case.case_id}: source_reference is not present in referenced evidence"
            )

    return {
        "dataset_id": dataset.dataset_id,
        "case_count": len(dataset.cases),
        "answerable_count": sum(case.answerable for case in dataset.cases),
        "unanswerable_count": sum(not case.answerable for case in dataset.cases),
        "referenced_document_count": len(declared_document_ids),
        "referenced_chunk_count": len(declared_chunk_ids),
        "status": "PASS",
    }
