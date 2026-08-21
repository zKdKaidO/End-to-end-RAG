import pytest

from app.db.database import SessionLocal
from evaluation.dataset_validator import DatasetValidationError, load_dataset, validate_dataset


def test_legal_eval_v1_dataset_references_real_indexed_corpus():
    dataset = load_dataset("evaluation/datasets/legal_eval_v1.json")
    db = SessionLocal()
    try:
        result = validate_dataset(dataset, db)
    finally:
        db.close()
    assert result == {
        "dataset_id": "legal_eval_v1",
        "case_count": 32,
        "answerable_count": 27,
        "unanswerable_count": 5,
        "referenced_document_count": 1,
        "referenced_chunk_count": 32,
        "status": "PASS",
    }


def test_legal_eval_v2_dataset_references_real_indexed_corpus():
    dataset = load_dataset("evaluation/datasets/legal_eval_v2.json")
    db = SessionLocal()
    try:
        result = validate_dataset(dataset, db)
    finally:
        db.close()
    assert result == {
        "dataset_id": "legal_eval_v2",
        "case_count": 65,
        "answerable_count": 55,
        "unanswerable_count": 10,
        "referenced_document_count": 3,
        "referenced_chunk_count": 70,
        "status": "PASS",
    }


def test_dataset_validator_rejects_duplicate_case_ids():
    dataset = load_dataset("evaluation/datasets/legal_eval_v1.json")
    dataset.cases.append(dataset.cases[0])
    db = SessionLocal()
    try:
        with pytest.raises(DatasetValidationError, match="unique"):
            validate_dataset(dataset, db)
    finally:
        db.close()
