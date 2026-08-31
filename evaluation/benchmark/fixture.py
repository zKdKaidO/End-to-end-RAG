"""Frozen fixture helpers for the isolated benchmark environment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


FIXTURE_PATH = Path("evaluation/benchmark/fixtures/legal_retrieval_v1.json")


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def fixture_sha256() -> str:
    return hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
