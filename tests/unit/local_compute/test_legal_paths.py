from __future__ import annotations

import sqlite3

from app.local_compute.legal_paths import LegalPathSource, LocalArtifactLegalPathResolver


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.executescript(
        """
        CREATE TABLE legal_units(id TEXT PRIMARY KEY, parent_id TEXT, unit_type TEXT, unit_number TEXT, unit_title TEXT, char_start INTEGER, char_end INTEGER);
        CREATE TABLE reconstruction(id INTEGER PRIMARY KEY, normalized_text TEXT);
        """
    )
    return db


def test_clean_repository_reconstructs_parent_chain():
    db = _db()
    db.execute("INSERT INTO reconstruction VALUES(1, ?)", ("Điều 11. Nghiên cứu.\n1. Nội dung.",))
    db.executemany("INSERT INTO legal_units VALUES(?,?,?,?,?,?,?)", [
        ("article-11", None, "ARTICLE", "11", "Nghiên cứu", 0, 30),
        ("clause-1", "article-11", "CLAUSE", "1", "", 18, 30),
    ])
    path = LocalArtifactLegalPathResolver(db).resolve("clause-1")
    assert path is not None
    assert path.path_source == LegalPathSource.LEGAL_UNIT_REPOSITORY
    assert path.ancestor_unit_ids == ("article-11", "clause-1")
    assert path.category_root_id == "article-11"


def test_polluted_metadata_is_repaired_from_reconstruction_without_overriding_path():
    db = _db()
    text = "Chương III\nCẬP NHẬT\nĐiều 11. Nghiên cứu khoa học.\n1. Nội dung.\n"
    article_start = text.index("Điều 11")
    clause_start = text.index("1. Nội dung")
    db.execute("INSERT INTO reconstruction VALUES(1, ?)", (text,))
    # Legacy false-positive parent: it must not appear in the resolved path.
    db.executemany("INSERT INTO legal_units VALUES(?,?,?,?,?,?,?)", [
        ("bad-chapter", None, "CHAPTER", "tr", "ình: 17:03:43", 0, len(text)),
        ("chapter-iii", None, "CHAPTER", "III", "CẬP NHẬT", 0, len(text)),
        ("article-11", "bad-chapter", "ARTICLE", "11", "Nghiên cứu khoa học", article_start, len(text)),
        ("clause-1", "article-11", "CLAUSE", "1", "", clause_start, len(text)),
    ])
    path = LocalArtifactLegalPathResolver(db).resolve("clause-1")
    assert path is not None
    assert path.path_source == LegalPathSource.REPAIRED_LEGAL_UNIT_REPOSITORY
    assert any(label.startswith("Chương III") for label in path.ancestor_display_labels)
    assert all("17:03:43" not in label for label in path.ancestor_display_labels)
    assert path.category_root_id == "article-11"


def test_unavailable_id_fails_closed():
    db = _db()
    db.execute("INSERT INTO reconstruction VALUES(1, ?)", ("",))
    path = LocalArtifactLegalPathResolver(db).resolve("unknown")
    assert path is not None
    assert path.path_source == LegalPathSource.UNAVAILABLE
    assert path.ancestor_display_labels == ()
