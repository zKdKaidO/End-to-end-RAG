# Chat History V1 citation snapshots

Snapshots are created only for source IDs already accepted by Block 6. The history layer intersects
`GenerationResult.citations` with the selected evidence in the effective Block 5 package. It neither
accepts near-miss citation syntax nor makes a new semantic judgment.

For each cited source it stores the exact selected `content_text` and computes
`SHA256(evidence_text.encode("utf-8"))` with no whitespace or Unicode mutation. It also stores available
document SHA, filename/title, historical UUIDs, page/article/clause/point, metadata, and provenance.
Uncited or invalid evidence is not stored. `INSUFFICIENT_EVIDENCE` stores zero snapshots.

The context fingerprint is SHA-256 over canonical sorted-key JSON containing version 1, model ID,
prompt version, and the ordered selected evidence tuples (`source_id`, document/chunk IDs, exact
content SHA). The full ContextPackage is not retained.

## Derived current-source states

- `CURRENT_EQUIVALENT`: a current document with the same document SHA has a chunk with the same exact
  content SHA. UUID equality is not required.
- `SOURCE_UPDATED`: the original document UUID exists but its SHA differs.
- `SOURCE_UNAVAILABLE`: neither equivalence nor a strong update linkage can be proven.

Resolution is best effort and bulk-oriented: documents are loaded together, then chunks only for the
candidate documents. Failure to resolve never prevents snapshot rendering. Historical evidence and
answer text are never replaced by current text.
