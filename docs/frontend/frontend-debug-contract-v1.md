# Frontend Debug Contract V1

## Security boundary

Debug remains an internal development surface controlled by `DEBUG_UI_ENABLED` and backend environment checks. A 404 is treated as an intentional gate: internal navigation disappears and the route explains that diagnostics are disabled. Normal `/answer` and `/answer/stream` responses receive no debug flag or diagnostic payload.

## API mapping

| API | Frontend use |
| --- | --- |
| `GET /health` | Coarse public API availability only |
| `GET /internal/debug/status` | Internal-tool availability, local provider, model identifier |
| `POST /internal/debug/rag` | One real typed `DebugTrace` |
| `GET /internal/debug/chunks/{chunk_id}` | Exact stored source/provenance drawer |
| `GET /internal/debug/documents` | Corpus pipeline list and debug filters |
| `GET /internal/debug/documents/{document_id}` | Pipeline stages and stored chunk detail |
| Internal evaluation summary/cases/comparison | Frozen report browser |
| Internal evaluation case rerun | Explicit interactive rerun trace |

## Trace semantics

- Dense and lexical tables display only candidate IDs, documents, backend ranks/scores, and previews.
- RRF shows frozen fusion ordering and available branch ranks. Scores are labelled diagnostic signals, never confidence.
- Hierarchy shows server-provided candidate origin, direct-child relation, anchor identity, and context order.
- Context shows candidate/duplicate/selected/dropped counts, token budget, stop reason, and evidence in source order.
- Generation shows public status, authoritative answerability, citation validation, prompt version, model, safe usage/latency, and mapped citations.
- Expected/actual comparison appears only when an evaluation case supplies frozen ground truth. Ad-hoc traces explicitly say `NO_GROUND_TRUTH`.

System prompts, chain-of-thought, secrets, environment variables, query embeddings, and source-document dumps are not requested or rendered.

## Large payload strategy

Final retrieval/context summaries render first. Dense, lexical, hierarchy, raw metadata, and provider usage are native collapsed details. Tables use contained scrolling. Candidate and answer components are memoized. Virtualization was not added because bounded retrieval Top-K and frozen evaluation sizes do not justify its accessibility and maintenance cost. The corpus list was measured at more than 1,000 development records, so it progressively renders 100 rows at a time while search still covers the complete returned set.
