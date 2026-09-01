"""Read-only direct-child adapter over one user's active local artifacts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from app.retrieval.hierarchy_types import DirectChildRow

from .errors import LocalComputeError, LocalComputeErrorCode


class LocalHierarchyRepository:
    """Expose authoritative local legal-unit children to the frozen expander.

    Every lookup is tied to an active artifact selected by the local retrieval
    request.  A child is therefore never sourced from a different document or
    a stale artifact version.
    """

    def __init__(
        self,
        settings,
        catalog,
        document_artifacts: dict[str, str],
    ) -> None:
        self.settings = settings
        self.catalog = catalog
        self.document_artifacts = dict(document_artifacts)

    def lookup_direct_children(
        self,
        anchor_chunk_ids: Sequence[UUID],
        document_ids: Sequence[UUID],
    ) -> list[DirectChildRow]:
        allowed_documents = {str(value) for value in document_ids}
        rows: list[DirectChildRow] = []

        for anchor_chunk_id in anchor_chunk_ids:
            anchor_id = str(anchor_chunk_id)
            found = self._find_anchor(anchor_id, allowed_documents)
            if found is None:
                continue
            document_id, artifact_id, anchor_legal_unit_id = found
            rows.extend(
                self._children_for_anchor(
                    anchor_chunk_id,
                    UUID(anchor_legal_unit_id),
                    document_id,
                    artifact_id,
                )
            )
        return rows

    def _find_anchor(
        self,
        anchor_chunk_id: str,
        allowed_documents: set[str],
    ) -> tuple[str, str, str] | None:
        for document_id, artifact_id in self.document_artifacts.items():
            if allowed_documents and document_id not in allowed_documents:
                continue
            with self._connect_artifact(document_id, artifact_id) as db:
                row = db.execute(
                    "SELECT document_id, legal_unit_id FROM chunks WHERE id = ?",
                    (anchor_chunk_id,),
                ).fetchone()
            if row is None:
                continue
            stored_document_id, legal_unit_id = row
            if stored_document_id != document_id or legal_unit_id is None:
                raise LocalComputeError(
                    LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR,
                    "Local hierarchy anchor violates artifact document isolation.",
                )
            return document_id, artifact_id, legal_unit_id
        return None

    def _children_for_anchor(
        self,
        anchor_chunk_id: UUID,
        anchor_legal_unit_id: UUID,
        document_id: str,
        artifact_id: str,
    ) -> list[DirectChildRow]:
        with self._connect_artifact(document_id, artifact_id) as db:
            rows = db.execute(
                """
                SELECT
                    child.id,
                    child.char_start,
                    child.unit_type,
                    child.unit_number,
                    child.unit_title,
                    child_chunk.id,
                    child_chunk.chunk_index,
                    child_chunk.content_text,
                    child_chunk.metadata_json,
                    child_chunk.provenance_json,
                    child_chunk.document_id
                FROM legal_units AS child
                JOIN chunks AS child_chunk ON child_chunk.legal_unit_id = child.id
                WHERE child.parent_id = ?
                  AND child.id <> ?
                ORDER BY
                    child.char_start,
                    child.id,
                    child_chunk.chunk_index,
                    child_chunk.id
                """,
                (str(anchor_legal_unit_id), str(anchor_legal_unit_id)),
            ).fetchall()

        direct_children: list[DirectChildRow] = []
        for row in rows:
            if row[10] != document_id:
                raise LocalComputeError(
                    LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR,
                    "Local hierarchy child violates artifact document isolation.",
                )
            direct_children.append(
                DirectChildRow(
                    anchor_chunk_id=anchor_chunk_id,
                    anchor_legal_unit_id=anchor_legal_unit_id,
                    child_legal_unit_id=UUID(row[0]),
                    document_id=UUID(document_id),
                    child_char_start=row[1],
                    child_unit_type=row[2],
                    child_unit_number=row[3],
                    child_unit_title=row[4],
                    child_chunk_id=UUID(row[5]),
                    child_chunk_index=row[6],
                    content_text=row[7],
                    metadata_json=json.loads(row[8]),
                    provenance_json=json.loads(row[9]),
                )
            )
        return direct_children

    def _connect_artifact(self, document_id: str, artifact_id: str) -> sqlite3.Connection:
        path = self._artifact_path(document_id, artifact_id)
        if not path.is_file():
            raise LocalComputeError(
                LocalComputeErrorCode.CAPABILITY_UNAVAILABLE,
                "Active local artifact is unavailable.",
            )
        return sqlite3.connect(path)

    def _artifact_path(self, document_id: str, artifact_id: str) -> Path:
        with self.catalog._connect() as db:
            row = db.execute(
                """
                SELECT artifact.relative_path, artifact.document_id, artifact.state,
                       document.active_artifact_id
                FROM local_artifacts AS artifact
                JOIN local_documents AS document ON document.document_id = artifact.document_id
                WHERE artifact.artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()
        if row is None or row[1] != document_id or row[3] != artifact_id or row[2] not in {
            "PREPARED_NOT_INDEXED",
            "INDEX_READY",
        }:
            raise LocalComputeError(
                LocalComputeErrorCode.CAPABILITY_UNAVAILABLE,
                "Active local artifact is unavailable.",
            )
        return self.settings.data_root / row[0] / "artifact.sqlite3"
