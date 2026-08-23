# Chat Session + Persistent History V1

## Boundary

Chat History is a product layer around the existing Blocks 4–6 orchestration. It calls
`AnswerService.prepare()` and `stream_prepared()` directly. Retrieval, context construction,
generation model/profile/prompt, answerability parsing, citation validation, the stateless
`/answer` APIs, Debug, and Evaluation are unchanged. Prior messages are never supplied to RAG.

## API

The namespace is `/api/v1/chat`:

- `POST /sessions` creates a session (`New conversation` by default).
- `GET /sessions?limit=&cursor=` lists sessions with an opaque `(effective activity time, UUID)` keyset cursor.
- `GET /sessions/{id}` retrieves one session and reconciles a stale active turn.
- `PATCH /sessions/{id}` accepts only `{ "title": "..." }`.
- `DELETE /sessions/{id}` deletes the history aggregate, or returns `409 SESSION_BUSY` for a fresh active turn.
- `GET /sessions/{id}/messages?before_sequence=&limit=` returns an ascending page selected by the stable sequence key.
- `POST /sessions/{id}/turns/stream` accepts `client_turn_id`, `query`, and optional `document_ids`.

No message edit/delete API exists. Completed answers and user messages are immutable through
normal product APIs.

## Product stream transaction order

1. Lock the target session and lazily reconcile an orphan if needed.
2. Resolve idempotency and the one-active-turn rule.
3. In one transaction create the turn, committed user message, and streaming assistant placeholder;
   allocate two `sequence_no` values; snapshot document scope; set the deterministic first-query title.
4. Commit before retrieval/model work starts.
5. Stream provider output only in memory and over SSE; no per-token database writes.
6. Run the existing Block 6 final parser/validator.
7. Atomically write final assistant content/metadata, all validated citation snapshots, terminal
   assistant/turn states, and session activity time.
8. Emit SSE `done` only after that transaction commits.

Finalization failure rolls back the entire completion, marks the turn `FAILED` with
`HISTORY_FINALIZATION_FAILED` where possible, and emits `error`, never `done`.

## Frontend

`/ask` retains the legal-research query and Sources workspace and adds a compact server-backed
conversation rail. It supports create/open/rename/delete, message keyset loading, persistent turn
streaming, cancellation, terminal-state Retry, and historical citation inspection. History is not
stored in localStorage. Explicit Retry creates a new client turn ID; retrying the same uncertain
network submission must reuse the original ID.

## Limits

V1 has no authentication, conversational memory, branching, message editing/deletion, retention
policy, shared sessions, or background generation. One active turn is allowed per session.
