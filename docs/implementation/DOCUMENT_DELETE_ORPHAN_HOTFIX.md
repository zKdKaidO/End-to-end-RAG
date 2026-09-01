# Document Delete / Orphan Hotfix

## Scope

This is a canonical platform document-lifecycle repair. It does not change
Blocks 1–6, P2C.5C browser-compute protocols, retrieval, context construction,
generation, database schema, or frontend code.

## Root cause and former behavior

`DELETE /documents/{document_id}` used `revoke_private(user_id, document_id)`.
The normal library query intentionally exposes both private grants and global
grants. Consequently, a visible global-only document had no matching private
grant. The service treated that missing grant as `RESOURCE_NOT_FOUND`, even
though the canonical document and its global access row existed. The visible
`fake.pdf` records had exactly that state: global-only access, no source URI,
zero pages/chunks/indexes, and a failed indexing job.

The old path therefore confused a missing *private access row* with a missing
document. It did not reach canonical garbage collection for those visible
orphans.

## New deletion contract

`DocumentAccessService.revoke_from_library` resolves the caller-visible access
origin under a row lock:

- private grant: remove only the caller's private grant;
- global grant: an administrator may remove the global grant through the same
  library delete route;
- another user's private-only document or an absent document: preserve the
  existing non-disclosing `404 RESOURCE_NOT_FOUND` behavior.

After the access row is removed, garbage collection runs only when no private
or global references remain. Shared content is retained when another access
reference survives. This preserves the prior multi-user/global safety rule.

## Orphan-safe cleanup

Canonical GC locks and re-checks the document, then removes the owned source
object and relational aggregate. `MinioClient.delete` now explicitly treats
`NoSuchKey` as already absent; other object-store errors still surface as
`ObjectStorageError`. Thus an absent owned source object cannot trap visible
metadata, while unexpected storage failures are not falsely reported as a
successful cleanup.

The GC aggregate removes indexing jobs, ingestion jobs, pages, chunks and
chunk-index cascades, the canonical document, and dangling
`LocalDocumentManifest` metadata. A second internal GC invocation for an
already-deleted document is a safe no-op.

## Current synthetic-data cleanup

The cleanup selection was made before deletion and required a known test-only
filename plus its matching fixture signature. It removed 51 records:

| Fixture provenance | Filename/state | Count | Access/source signature |
|---|---|---:|---|
| indexing/RQ worker test | `fake.pdf` / `COMPLETED` | 17 | global-only; no source URI; zero derived rows; failed indexing job |
| upload storage-failure test | `mocked.pdf` / `FAILED` | 17 | private-only; no source URI; zero derived rows |
| upload queue-failure test | `mocked2.pdf` / `FAILED` | 17 | private-only; source URI; zero derived rows |

Cleanup used the same access-revocation and canonical-GC lifecycle as the
product. Result: 34 private grants and 17 global grants removed; all 51
documents were orphaned after revocation and physically/relationally cleaned.
No filename outside this positively identified set was selected by the cleanup
script.

## Test-corpus isolation

The affected legacy integration modules inserted test documents directly into
the normal development PostgreSQL/MinIO namespace. The explicitly marked
`isolated_document_corpus` fixture now snapshots document IDs before each such
test and, in teardown, removes only IDs created by that test along with their
owned object, access rows, jobs, pages, manifests, and canonical document.
Unmarked tests and pre-existing development documents are not candidates for
this fixture.

The marked modules are:

- `tests/integration/test_api.py`
- `tests/integration/test_indexing_rq_runtime.py`
- `tests/integration/test_processing_worker_failures.py`
- `tests/integration/test_rq_runtime.py`

Focused count checks proved the relevant test paths leave the normal document
count unchanged: `56 -> 56` before synthetic cleanup and `4 -> 4` after it.

## Verification

`tests/integration/test_document_delete_orphans.py` covers private failed
documents, processing partial state (page plus chunk), indexing failure,
zero-derived state, global-only orphan removal, shared-reference retention,
unauthorized/nonexistent `404`, missing-object idempotency, and repeat internal
GC. Focused result: `7 passed`.

Additional historically polluting upload/RQ cases passed with a stable corpus
count: `3 passed`, `4 -> 4`.

## Remaining limitation

The test fixture provides per-test cleanup inside the shared development stack;
it does not replace a future dedicated test database/object namespace. That
larger environment separation is intentionally outside this urgent lifecycle
hotfix.
