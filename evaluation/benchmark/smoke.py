"""Read-only retrieval proof for the isolated benchmark environment."""

from __future__ import annotations

import json
from time import perf_counter

from app.auth.scope import InternalRetrievalScope
from app.db.database import SessionLocal
from app.retrieval.schemas import RetrievalRequest
from app.retrieval.service import RetrievalService, validate_request
from evaluation.benchmark.fixture import load_fixture
from evaluation.benchmark.runtime import assert_benchmark_runtime
from evaluation.benchmark.snapshot import snapshot


def run() -> dict:
    assert_benchmark_runtime()
    before = snapshot()
    fixture = load_fixture()
    db = SessionLocal()
    try:
        started = perf_counter()
        results = RetrievalService(db, access_scope=InternalRetrievalScope("benchmark-readonly")).retrieve(
            validate_request(RetrievalRequest(query_text=fixture["smoke_query"]))
        )
        retrieval_ms = (perf_counter() - started) * 1000
    finally:
        db.close()
    after = snapshot()
    if before != after:
        raise RuntimeError("BENCHMARK_READ_ONLY_INTEGRITY_CHANGED")
    if not results:
        raise RuntimeError("BENCHMARK_RETRIEVAL_RETURNED_NO_RESULTS")
    return {
        "results": len(results), "first_document_id": results[0]["document_id"],
        "retrieval_ms": round(retrieval_ms, 3), "before": before, "after": after,
        "generation_called": False,
    }


def main() -> None:
    print(json.dumps(run(), sort_keys=True))


if __name__ == "__main__":
    main()
