# Chat History V1 data contract

The migration revision is `chat_session_history_v1`, after `block_3_indexing_models`. It adds
exactly four tables.

## `chat_sessions`

UUID `id`; non-null title/created/updated timestamps; nullable `last_message_at` and `deleted_at`.
Session ordering uses `coalesce(last_message_at, created_at)` plus UUID as a deterministic keyset.

## `chat_turns`

Contains the session FK, client UUID, canonical 64-character request hash, state, lightweight JSONB
document-scope snapshot, timestamps, and safe failure fields. Database controls:

- `uq_chat_turn_session_client` on `(session_id, client_turn_id)`;
- partial unique index `uq_chat_turn_one_active_per_session` on `session_id` for `PENDING`/`STREAMING`;
- state check and `COMPLETED => completed_at IS NOT NULL` check;
- session/created index.

## `chat_messages`

Contains session/turn FKs, `USER` or `ASSISTANT`, non-null `sequence_no`, content/delivery state,
nullable authoritative answer status, safe generation identity/usage fields, JSONB operational
metadata, and timestamps. `uq_chat_message_session_sequence` is the ordering authority. Checks
require finalized timestamps on completed messages and null answer status on failed/cancelled ones.

## `message_citation_snapshots`

Contains message ownership, citation label/order, historical source UUIDs, source identity/hashes,
legal/page coordinates, exact evidence text, metadata/provenance JSONB, version, and timestamp.
Labels and orders are unique within a message.

Historical `original_document_id`, `original_chunk_id`, and `original_legal_unit_id` deliberately
have no foreign keys. Source deletion/reprocessing therefore cannot cascade into history. The only
cascades are session → turn/message → snapshot.

## Prohibited persisted data

The schema contains no full ContextPackage, candidate pools, DebugTrace, system prompt text, hidden
reasoning, provider raw messages, environment variables, authorization headers, or secrets.
`prompt_hash` stores only SHA-256 of the selected frozen system prompt.
