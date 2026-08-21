from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.retrieval.hierarchy_types import DirectChildRow


class HierarchyRepository:
    """Read-only, one-query repository for authoritative direct children."""

    def __init__(self, db: Session):
        self.db = db

    def lookup_direct_children(
        self,
        anchor_chunk_ids: Sequence[UUID],
        document_ids: Sequence[UUID],
    ) -> list[DirectChildRow]:
        if not anchor_chunk_ids:
            return []

        rows = self.db.execute(
            text(
                """
                WITH requested_anchors AS (
                    SELECT anchor_chunk_id, anchor_order
                    FROM unnest(CAST(:anchor_chunk_ids AS uuid[]))
                         WITH ORDINALITY AS requested(anchor_chunk_id, anchor_order)
                ),
                anchors AS (
                    SELECT
                        requested.anchor_order,
                        c.id AS anchor_chunk_id,
                        c.document_id,
                        c.legal_unit_id
                    FROM requested_anchors AS requested
                    JOIN chunks AS c ON c.id = requested.anchor_chunk_id
                    WHERE c.legal_unit_id IS NOT NULL
                      AND (
                        NOT CAST(:document_filter_enabled AS boolean)
                        OR c.document_id = ANY(CAST(:document_ids AS uuid[]))
                      )
                )
                SELECT
                    anchors.anchor_chunk_id,
                    anchors.legal_unit_id AS anchor_legal_unit_id,
                    child.id AS child_legal_unit_id,
                    child.document_id,
                    child.char_start AS child_char_start,
                    child.unit_type AS child_unit_type,
                    child.unit_number AS child_unit_number,
                    child.unit_title AS child_unit_title,
                    child_chunk.id AS child_chunk_id,
                    child_chunk.chunk_index AS child_chunk_index,
                    child_chunk.content_text,
                    child_chunk.metadata_json,
                    child_chunk.provenance_json
                FROM anchors
                JOIN legal_units AS child
                  ON child.parent_unit_id = anchors.legal_unit_id
                 AND child.document_id = anchors.document_id
                 AND child.id <> anchors.legal_unit_id
                JOIN chunks AS child_chunk
                  ON child_chunk.legal_unit_id = child.id
                 AND child_chunk.document_id = anchors.document_id
                WHERE (
                    NOT CAST(:document_filter_enabled AS boolean)
                    OR child_chunk.document_id = ANY(CAST(:document_ids AS uuid[]))
                )
                ORDER BY
                    anchors.anchor_order,
                    child.char_start,
                    child.id,
                    child_chunk.chunk_index,
                    child_chunk.id
                """
            ),
            {
                "anchor_chunk_ids": [str(value) for value in anchor_chunk_ids],
                "document_filter_enabled": bool(document_ids),
                "document_ids": [str(value) for value in document_ids],
            },
        ).mappings().all()

        return [
            DirectChildRow(
                anchor_chunk_id=row["anchor_chunk_id"],
                anchor_legal_unit_id=row["anchor_legal_unit_id"],
                child_legal_unit_id=row["child_legal_unit_id"],
                document_id=row["document_id"],
                child_char_start=row["child_char_start"],
                child_unit_type=row["child_unit_type"],
                child_unit_number=row["child_unit_number"],
                child_unit_title=row["child_unit_title"],
                child_chunk_id=row["child_chunk_id"],
                child_chunk_index=row["child_chunk_index"],
                content_text=row["content_text"],
                metadata_json=row["metadata_json"],
                provenance_json=row["provenance_json"],
            )
            for row in rows
        ]

