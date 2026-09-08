"""Authoritative, artifact-local legal identity resolution.

Chunk metadata is descriptive document metadata, not legal structure.  This
module derives legal paths exclusively from the artifact's legal-unit graph.
For legacy artifacts that contain a recognizer false positive, it rebuilds an
in-memory graph from the already-persisted reconstruction text.  That repair
does not touch chunks, embeddings, or the SQLite artifact on disk.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from enum import Enum

from app.processing.parser import LegalParser, LegalUnitData


class LegalPathSource(str, Enum):
    LEGAL_UNIT_REPOSITORY = "LEGAL_UNIT_REPOSITORY"
    REPAIRED_LEGAL_UNIT_REPOSITORY = "REPAIRED_LEGAL_UNIT_REPOSITORY"
    UNAVAILABLE = "UNAVAILABLE"


_TYPE_LABELS = {
    "PART": "Phần", "APPENDIX": "Phụ lục", "CHAPTER": "Chương", "SECTION": "Mục",
    "TABLE_CATEGORY": "Danh mục",
    "ARTICLE": "Điều", "CLAUSE": "Khoản", "POINT": "Điểm",
}
_ROMAN = re.compile(r"^[IVXLCDM]+$")
_TIMESTAMP = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")


@dataclass(frozen=True)
class AuthoritativeLegalPath:
    legal_unit_id: str
    unit_type: str | None
    display_label: str | None
    ancestor_unit_ids: tuple[str, ...]
    ancestor_display_labels: tuple[str, ...]
    category_root_id: str | None
    path_source: LegalPathSource

    @property
    def labels(self) -> tuple[str, ...]:
        return self.ancestor_display_labels

    def as_metadata(self) -> dict[str, object]:
        return {
            "legal_unit_id": self.legal_unit_id,
            "unit_type": self.unit_type,
            "display_label": self.display_label,
            "ancestor_unit_ids": list(self.ancestor_unit_ids),
            "ancestor_display_labels": list(self.ancestor_display_labels),
            "category_root_id": self.category_root_id,
            "path_source": self.path_source.value,
        }


@dataclass(frozen=True)
class _Unit:
    key: str
    parent_key: str | None
    unit_type: str
    unit_number: str
    title: str
    start: int
    end: int


def _label(unit: _Unit) -> str:
    kind = _TYPE_LABELS.get(unit.unit_type, unit.unit_type)
    number = f" {unit.unit_number}" if unit.unit_number else ""
    title = f" — {unit.title}" if unit.title else ""
    return f"{kind}{number}{title}"


def _persisted_unit_is_sane(unit_type: str | None, number: str | None, title: str | None) -> bool:
    if unit_type == "PREAMBLE":
        return True
    if unit_type not in _TYPE_LABELS:
        return False
    value = (number or "").strip()
    if unit_type in {"PART", "CHAPTER"} and not _ROMAN.fullmatch(value):
        return False
    if unit_type in {"SECTION", "ARTICLE", "CLAUSE"} and not value.isdigit():
        return False
    if unit_type == "POINT" and not re.fullmatch(r"[a-zđ]", value):
        return False
    return not _TIMESTAMP.search(title or "")


class LocalArtifactLegalPathResolver:
    """Resolve paths for one artifact without trusting chunk metadata."""

    def __init__(self, db: sqlite3.Connection) -> None:
        stored = [
            _Unit(
                key=row[0], parent_key=row[1], unit_type=row[2],
                unit_number=row[3] or "", title=row[4] or "",
                start=int(row[5] or 0), end=int(row[6] or 0),
            )
            for row in db.execute(
                "SELECT id, parent_id, unit_type, unit_number, unit_title, char_start, char_end FROM legal_units"
            )
        ]
        self._units: dict[str, _Unit] = {unit.key: unit for unit in stored}
        self._source = (
            LegalPathSource.LEGAL_UNIT_REPOSITORY
            if all(_persisted_unit_is_sane(unit.unit_type, unit.unit_number, unit.title) for unit in stored)
            else LegalPathSource.REPAIRED_LEGAL_UNIT_REPOSITORY
        )
        if self._source == LegalPathSource.REPAIRED_LEGAL_UNIT_REPOSITORY:
            self._replace_with_reconstructed_units(db, stored)

    @property
    def source(self) -> LegalPathSource:
        return self._source

    def resolve(self, legal_unit_id: str | None) -> AuthoritativeLegalPath | None:
        if not legal_unit_id:
            return None
        unit = self._units.get(legal_unit_id)
        if unit is None:
            return AuthoritativeLegalPath(
                legal_unit_id=legal_unit_id, unit_type=None, display_label=None,
                ancestor_unit_ids=(), ancestor_display_labels=(), category_root_id=None,
                path_source=LegalPathSource.UNAVAILABLE,
            )
        return self._path_for_unit(unit, legal_unit_id)

    def resolve_for_span(
        self, legal_unit_id: str | None, char_start: int | None, char_end: int | None,
    ) -> AuthoritativeLegalPath | None:
        resolved = self.resolve(legal_unit_id)
        if resolved is not None and resolved.path_source != LegalPathSource.UNAVAILABLE:
            return resolved
        if char_start is None or char_end is None or char_end <= char_start:
            return resolved
        # Legacy chunks sometimes inherited one false-positive parent across a
        # table. Rebind only to a reconstructed semantic heading whose start
        # lies inside the chunk span; this is source-offset reconstruction, not
        # textual guessing. First heading wins so adjacent categories are not
        # silently merged.
        candidates = [
            unit for unit in self._units.values()
            if unit.key.startswith("repaired:")
            and unit.unit_type in {"TABLE_CATEGORY", "ARTICLE"}
            and char_start <= unit.start < char_end
        ]
        if not candidates:
            return resolved
        candidates.sort(key=lambda unit: (unit.start, unit.key))
        return self._path_for_unit(candidates[0], candidates[0].key)

    def _path_for_unit(self, unit: _Unit, legal_unit_id: str) -> AuthoritativeLegalPath:
        chain: list[_Unit] = []
        current: _Unit | None = unit
        visited: set[str] = set()
        while current is not None and current.key not in visited:
            visited.add(current.key)
            if current.unit_type != "PREAMBLE":
                chain.append(current)
            current = self._units.get(current.parent_key or "")
        chain.reverse()
        labels = tuple(_label(item) for item in chain)
        category = next(
            (
                item.key for item in reversed(chain)
                if item.unit_type in {"TABLE_CATEGORY", "ARTICLE", "SECTION"}
            ),
            None,
        )
        return AuthoritativeLegalPath(
            legal_unit_id=legal_unit_id,
            unit_type=unit.unit_type,
            display_label=_label(unit) if unit.unit_type != "PREAMBLE" else None,
            ancestor_unit_ids=tuple(item.key for item in chain),
            ancestor_display_labels=labels,
            category_root_id=category,
            path_source=self._source,
        )

    def _replace_with_reconstructed_units(self, db: sqlite3.Connection, stored: list[_Unit]) -> None:
        row = db.execute("SELECT normalized_text FROM reconstruction WHERE id=1").fetchone()
        if row is None or not isinstance(row[0], str):
            self._units = {}
            self._source = LegalPathSource.UNAVAILABLE
            return
        rebuilt: list[_Unit] = []

        def visit(node: LegalUnitData, parent_key: str | None) -> None:
            key = f"repaired:{node.unit_type}:{node.unit_number}:{node.start_char}"
            rebuilt.append(_Unit(
                key, parent_key, node.unit_type, node.unit_number, node.title,
                node.start_char, node.end_char,
            ))
            for child in node.children:
                visit(child, key)

        for root in LegalParser().parse(row[0]):
            visit(root, None)
        # Existing chunks and expansion APIs retain their persisted UUIDs. Map
        # each old unit to the exact reconstructed unit with the same type,
        # number and source offset. This gives legacy evidence its repaired
        # ancestry without rewriting an artifact or its vectors.
        available = {(item.unit_type, item.unit_number, item.start): item for item in rebuilt}
        key_by_rebuilt = {item.key: item for item in rebuilt}
        mapped: dict[str, _Unit] = {}
        old_key_by_signature = {
            (prior.unit_type, prior.unit_number, prior.start): prior.key
            for prior in stored
        }
        for old in stored:
            replacement = available.get((old.unit_type, old.unit_number, old.start))
            if replacement is None:
                continue
            parent_id = None
            if replacement.parent_key:
                parent_rebuilt = key_by_rebuilt[replacement.parent_key]
                parent_id = old_key_by_signature.get(
                    (parent_rebuilt.unit_type, parent_rebuilt.unit_number, parent_rebuilt.start),
                    parent_rebuilt.key,
                )
            mapped[old.key] = _Unit(
                old.key, parent_id, replacement.unit_type, replacement.unit_number,
                replacement.title, replacement.start, replacement.end,
            )
        # Reconstructed-only ancestors (for example an Article whose legacy
        # artifact never recognized its heading) stay addressable through a
        # stable runtime ID. Chunks retain their original UUIDs; only their
        # authoritative ancestor chain uses this in-memory bridge.
        self._units = {**key_by_rebuilt, **mapped}
