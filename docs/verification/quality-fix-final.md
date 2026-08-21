# Targeted RAG Quality Fixes V1 — Refreeze Audit

Date: 2026-08-19

## Mandatory criteria

- Frozen dataset SHA-256 unchanged: PASS
- Full regression, 0 failed: PASS (182/182)
- New production database tables: 0 (public table count remains 10)
- Block 5 changed: NO
- Structured answerability marker and deterministic parser: PASS
- Marker hidden from HTTP and SSE public output: PASS
- Five frozen unanswerable cases mapped to `INSUFFICIENT_EVIDENCE`: 5/5
- Unsupported direct answers for unanswerable cases: 0/5
- Second answerability LLM call: NONE
- Citation exact-syntax reinforcement: PASS
- Natural-language lexical branch no longer universally empty: PASS (6/32 cases)
- Safe parameterized lexical construction: PASS
- Dense retrieval, RRF, Top-K, and document-filter contract unchanged: PASS
- Cosine answerability threshold: NOT IMPLEMENTED
- Reranker: NOT IMPLEMENTED
- Redis/RQ added by this phase: NO

## Narrow contract amendments

- Block 4: lexical natural-language query semantics only.
- Block 6: authoritative answerability output protocol and `legal-rag-v2` citation/abstention instructions.

## Explicitly unchanged

Blocks 1–3; Block 4 dense retrieval and RRF; Block 5; Block 6 async/provider architecture, provenance mapping, and public SSE event contract.

## Decision

TARGETED QUALITY FIXES READY TO REFREEZE.
