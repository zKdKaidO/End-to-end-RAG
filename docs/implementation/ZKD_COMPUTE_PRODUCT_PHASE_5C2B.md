# ZKD Compute Product Phase 5C.2B — Documents Local-First Product Wiring

## Scope

`/documents` now uses the production `BrowserComputeClient` for the selected
ZKD Compute device. This phase changes data plumbing and behavior only; the
human-owned Documents visual hierarchy, CSS, dialog, product shell, and Ask
page remain unchanged.

## Data-flow change

The historical page used platform content endpoints for list, detail, upload,
index, and delete. The active Documents flow is now:

```text
Browser DocumentsPage
  -> BrowserComputeClient
  -> authenticated 127.0.0.1 ZKD Compute
```

The platform continues to provide authentication, device discovery, and local
session grants through the client. It receives no PDF bytes, extracted text,
chunks, vectors, prompts, or answers from this page.

## Device and session behavior

The page owns one stable, page-scoped `BrowserComputeClient`; it is not
recreated per render and stores no secrets in React state or browser storage.
On mount and Refresh it discovers, connects to exactly one usable `READY`
device for the `documents` operation, then reads `compute.listDocuments()`.

No device, unavailable Compute, or more than one usable device produces the
existing error surface. The page neither selects a device at random nor falls
back to platform document-content APIs. A device-picker is a future UX task.
Read calls use the client’s existing session/bootstrap behavior. Mutation calls
are not automatically replayed after an ambiguous local network failure.

## Local catalog presentation

The local list is authoritative while Compute is available. The page maps only
the documented local fields: opaque `document_id`, `original_filename`, byte
size, preparation/index states, safe failure code, timestamps, page count, and
chunk count. It does not invent canonical platform IDs, legal-unit counts,
access grants, indexing counts, or chunks.

`INDEX_READY` maps to Ready; active preparation/index states map to Processing
or Indexing; `PREPARED_NOT_INDEXED`/`NOT_INDEXED` maps to Prepared and exposes
the existing Index action; a local failure maps to Failed and remains deletable
without a fake retry action. Metric cards and client-side search/filter operate
only on this local catalog.

## Lifecycle actions and privacy

Upload generates a fresh browser UUID because the existing local source route
requires a caller-supplied opaque document identity. It sends the selected PDF
only through `compute.uploadSource(documentId, file, file.name)`, then calls
`compute.prepareDocument(documentId)`. The existing Index and Remove controls
call `compute.indexDocument` and `compute.deleteDocument` respectively, then
refresh the local catalog. The visible historical Access selector remains
non-operative because the local document contract has no equivalent local
private/global storage semantic.

The detail drawer reads only the already loaded local metadata. It does not
call the legacy platform detail API and reports the existing empty state for
chunk content, because the local catalog intentionally exposes no chunk text.

## Polling and offline behavior

While a local document is active, the page polls the local list at the existing
four-second cadence, pauses/reduces work while the tab is hidden, and backs off
after failures. It becomes idle after terminal states. If Compute is offline,
content mutations are logically disabled and the page surfaces the local error;
it does not present platform document content as a substitute. Metadata-only
manifest fallback is deliberately deferred because the current page has no
non-operable offline presentation treatment.

## Verification

`frontend/src/pages/DocumentsPage.test.tsx` verifies local catalog metrics,
search/filter, local upload/prepare/index/delete, metadata-only detail,
refresh, polling, offline/multiple-device error behavior, and that the legacy
`api.documents`, `api.document`, `api.upload`, `api.indexDocument`, and
`api.deleteDocument` methods are never called. The upload test passes a
synthetic PDF `File` to the Compute client and proves no platform API mock
receives it.

The browser-client protocol and local lifecycle tests remain the integration
coverage for authenticated local routes. A real Chrome/Edge PNA/CORS run was
not available in this phase: `BROWSER_ACCEPTANCE_NOT_EXECUTABLE`.

## Known limitations and next phase

- Real Chrome/Edge PNA/CORS acceptance is unresolved.
- A multiple-device selector UI is not implemented.
- AskPage remains on its current data flow.
- Production OS credential-store hardening and installer packaging are pending.
- Authenticated real local generation acceptance is pending.
- Metadata-only offline document UX is intentionally limited.

Next phase: `P2C.5C.3 ASK LOCAL-FIRST PRODUCT INTEGRATION`.
