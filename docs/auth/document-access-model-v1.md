# Document Access Model V1

Canonical bytes remain represented once by `documents.sha256`. Authorization is represented separately:

```text
users ──< document_access_grants >── documents
                                      ^
global_document_access ───────────────┘
```

A user may read a document when either `(document_id, user_id)` exists in `document_access_grants` or `document_id` exists in `global_document_access`. `documents.user_id` is legacy/provenance-only and is never authorization truth.

Uploads are private by default. Only an `ADMIN` may request a Global upload or alter Global access. Canonical dedup is cross-user: identical bytes produce one document while each user receives an independent grant. Private and Global references may coexist and the UI reports `PRIVATE`, `GLOBAL`, or `PRIVATE + GLOBAL`.

Revoking private access removes only that user's grant. Revoking Global removes only the Global reference. The canonical document becomes GC-eligible only when no private or Global references remain.

All document, page, chunk, ingestion/indexing job, and current-source APIs reauthorize the referenced document. Hidden and nonexistent UUIDs share `404 RESOURCE_NOT_FOUND` semantics.
