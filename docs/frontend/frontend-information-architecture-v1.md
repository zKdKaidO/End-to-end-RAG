# Frontend Information Architecture V1

## Route model

The top-level product remains deliberately small:

| Route | Purpose | Primary backend contract |
| --- | --- | --- |
| `/ask` | Grounded research answer and exact source inspection | `POST /answer/stream` |
| `/documents` | Corpus upload and frozen pipeline lineage | `POST /documents`, internal document views when enabled |
| `/debug` | Development pipeline trace | `POST /internal/debug/rag` and internal chunk/document reads |
| `/evaluation` | Frozen benchmark inspection and labelled single-case rerun | internal evaluation reads/rerun |

Unknown routes return to `/ask`, the primary product workflow. Debug and Evaluation navigation is removed when `/internal/debug/status` returns the backend's intentional 404 gate. The frontend does not weaken that gate.

## Shell

The shell owns only route navigation, appearance preference, and coarse API/provider availability. It never owns answer tokens or diagnostic payloads. This keeps streaming state local to the research session and prevents shell/navigation updates for each provider delta.

## Documents

The list surface provides corpus totals, filename/ID search, upload, refresh, stage badges, and concise page/chunk counts. Selecting a row opens a drawer with backend-provided lifecycle status, counts, identifiers, chunks, metadata, and provenance. It does not derive legal hierarchy or reinterpret processing status.

Upload states are explicit: submitting, accepted, backend failure, and refreshed stored state. Continued processing and indexing are rendered from their server statuses.

## Ask

The composer remains outside `ResearchSession`. Submitting creates an immutable request descriptor; the child session owns its AbortController, buffered answer, terminal result, and source selection.

Desktop uses an approximately 68/32 horizontal split. Sources can be resized, collapsed, or restored. Clicking a valid `[Sx]` citation expands the panel, activates the exact source row, and scrolls it into view. Narrow screens use the same citation contract through a modal source drawer.

Only backend-mapped citations become controls. Missing or invalid citations are never guessed. `INSUFFICIENT_EVIDENCE` and warning states retain their authoritative labels.

## Debug

The trace is organized as QUERY → DENSE → LEXICAL → RRF → HIERARCHY → CONTEXT → GENERATION. Summary metrics and final RRF are visible first; candidate pools, hierarchy payload, metadata, and provider-safe fields use progressive disclosure. Raw JSON is a fallback for structured metadata, never the primary trace.

## Evaluation

Evaluation exposes compact measured aggregates, dataset fingerprint, failure filters, text search, case list, before/after table, and known limitations. The detail drawer keeps frozen expected data beside measured output. A rerun is explicitly labelled “Interactive rerun”; it is not presented as frozen benchmark truth.

## State ownership

- Server truth stays in typed response objects from `frontend/src/api/client.ts`.
- Local component state handles UI selection, filters, drawers, and request lifecycle.
- The browser does not rerank, fuse, infer answerability, validate legal claims, reconstruct citations, or reorder evidence.
- No global store was needed.
