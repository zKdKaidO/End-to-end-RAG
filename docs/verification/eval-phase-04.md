# RAG Evaluation Gate V1 — Phase 04 Real baseline run

Executed all 32 cases sequentially through real E5 query embedding, PostgreSQL pgvector and FTS branches, Python RRF, frozen Block 5 with the production Qwen tokenizer, and real Ollama `qwen3.5:9b` streaming generation. No generation parameter was changed and no mocks were used.

Measured aggregate:

- Hit@1 85.19%; Hit@3/5/10 92.59%; MRR 0.8889.
- Context retention 100% for the 25 cases whose complete expected solution reached Block 4 final Top-10; no expected evidence was dropped by Block 5.
- Citation presence and structural validity 88.89%; expected-source match 81.48%; invalid citations 0%; missing citations 11.11%.
- Correct abstention 0%; unsupported answer rate 100% across five unanswerable cases.
- Failures: 2 retrieval misses, 2 missing-citation, 1 wrong-source, 5 unsupported-answer; 22 cases passed all deterministic checks.
- Mean latency: retrieval 41.99ms, context 18.42ms, TTFT 608.42ms, generation 3,084.57ms, total 3,401.81ms.
- Lexical candidates were zero in all 32 cases; the measured hybrid path was effectively dense-only on this corpus.

Result: PASS as a baseline measurement, not as a production-quality gate.
