# ZKD Compute Product Phase 5C.3B — Ask Local-First Page Wiring

## Scope

This phase wires the active `/ask` content path to authenticated local ZKD
Compute. It preserves the existing human-owned CSS, visual class names, layout,
icons, and product shell. It does not change Blocks 1–6, local runtime routes,
retrieval/context/generation semantics, provider configuration, or document
page behavior.

The page owns one stable, page-scoped `BrowserComputeClient`. Navigation may
therefore require another discovery/grant/bootstrap after Documents; an
app-scoped in-memory client remains a future optimization, not a prerequisite.

## Old and new data flow

The historical Ask path used platform document APIs, platform chat-session and
history APIs, platform SSE turn streaming, and a platform chunk lookup from the
source drawer. That would expose query, answer, history, and document-derived
content to the platform.

The active V1 flow is now:

```text
AskPage browser memory
  -> BrowserComputeClient
  -> authenticated 127.0.0.1 ZKD Compute
  -> local retrieval + Block 5 + legal-rag-v2 + local/user-cloud provider
  -> structured local answer + citations
  -> browser memory
```

The platform is reached only indirectly by `BrowserComputeClient` for device
discovery and local-session grant issuance. The Ask page has no active calls to
`api.documents`, `api.chat*`, `streamChatTurn`, or `api.chunk`.

## Local source catalog and scope

On mount, Ask asks the client to connect for the `answer` capability, then
loads `compute.listDocuments()`. Only local documents with both
`preparation_state` and `index_state` equal to `INDEX_READY` are presented.
The page uses a narrow local source adapter containing only the real local
document ID, filename, page count, and chunk count.

The selected IDs are device-local. A device change clears the transcript and
reinitializes selection from that device's catalog, so source IDs from another
device cannot be submitted as portable IDs.

- All selected local sources become `document_ids: null`.
- A non-empty explicit subset is sent unchanged.
- If queryable sources exist and none is selected, submit is disabled.
- The browser-client `EMPTY_DOCUMENT_SCOPE` guard remains a second boundary;
  Ask never sends `[]` expecting a zero-document query.

## Answer-only, non-streaming conversation

Each explicit submit creates a browser-memory user message and pending assistant
message, then calls `compute.answer()` exactly once. It does not call
`compute.query()`: local answer already performs canonical retrieval, hierarchy,
Block 5 context construction, `legal-rag-v2` generation, and citation mapping.

The local route returns synchronous JSON. While awaiting it, the existing chat
shell renders its pending state. On completion, the result replaces that state;
there are no fabricated token deltas or SSE events.

`LOCAL_ANSWER_CANCEL_GAP` remains explicit. The streaming Stop control is not
shown for the local synchronous path. Browser unmount/network cleanup is not
described as provider/model cancellation, and no answer request is retried
automatically after an ambiguous failure.

## Browser-memory transcript and history

The current transcript lives only in React memory. New clears messages, pending
state, transient errors, and active citation state, then returns to `/ask`.
No platform session is created and `/ask/:sessionId` is redirected to `/ask`;
there is no persisted-session implication. Recent history, rename, delete,
older-history, and reload restoration are intentionally absent in V1. Query,
answer, citation, and scope content are not written to localStorage,
sessionStorage, IndexedDB, cookies, or platform chat APIs. The unrelated visual
sidebar-collapse preference remains the pre-existing layout preference.

An explicit Retry uses the failed browser-memory user query and current source
scope to make a new local `answer` request. BrowserComputeClient provides the
fresh signed request envelope; no platform history lookup or cached answer is
used.

## Citations and source panel

Local citations are mapped from the real shape:

```text
source_id, chunk_id, document_id, metadata_json, provenance_json
```

Answer text is preserved, including canonical `[S1]`, `[S2]`, … markers. A
citation's source label is `source_id`; a known local document ID maps to its
currently loaded local filename. Page values are shown only when they are safe
positive integers from provenance.

`SourcePanel` now accepts narrow local source and local citation types. It no
longer requires `citation_label`, `snippet`, or `content_preview`; it displays
the truthful local-preview-unavailable state instead. It does not import or
call a platform evidence API. Generic metadata/provenance is not blindly dumped
into the panel, so filesystem paths and unrelated runtime fields are not
rendered. Full evidence preview remains deferred until a dedicated local,
authorized evidence endpoint exists.

The old `SourceDrawer` platform `api.chunk` path is absent from the active Ask
flow.

## Provider, availability, and outage behavior

Ask submits the canonical default local route with no browser-provided endpoint
or credential. The local router remains authoritative for `LOCAL` and optional
configured `USER_CLOUD` routing; `PLATFORM_CLOUD` remains disabled. The current
Ask UI has no safe UserCloud configuration selector, so local routing is the V1
product path and UserCloud selection UI is deferred.

With a valid local browser session, answer work proceeds during platform outage
without per-answer rediscovery. BrowserComputeClient may bootstrap before a new
answer if its session expired; it does not auto-replay a request already sent.
If local Compute is unavailable or multiple compatible devices exist, the page
uses the existing typed error surface and does not fall back to platform
retrieval or generation.

## Verification

- `frontend/src/pages/AskPage.test.tsx`: local catalog/admission, all and subset
  scope, zero selection, one answer/no query, deferred synchronous pending and
  completion, exact inline citation preservation, no Stop, explicit retry, New
  transcript reset, fresh-mount loss of history, selected-device error, and a
  `PRIVATE_LOCAL_QUERY_SENTINEL` privacy check.
- `frontend/src/components/ask/SourcePanel.test.tsx`: real local citation
  fields, `source_id` label, safe page display, no fake preview, and no render
  of unsafe provenance path data.
- Combined Ask, SourcePanel, browser Compute, and preserved Documents frontend
  tests: **31 passed**.
- `npm run build`: **PASS**.
- Existing BrowserCompute tests retain session expiry, local-outage continuation,
  device selection, signed request, and no platform content request coverage.
- Previous unchanged temporary-root authenticated real generation acceptance is
  retained: `AUTHENTICATED_LOCAL_GENERATION_PASS` with `qwen3.5:9b`.

## Known V1 limitations and next phase

- No persistent chat history; reload loses transcript.
- No answer streaming.
- `LOCAL_ANSWER_CANCEL_GAP`.
- Full citation evidence preview deferred.
- Multiple-device selector UI deferred.
- Real Chrome/Edge PNA/CORS acceptance unresolved.
- Page-scoped client can rebootstrap across navigation.
- Production OS credential store and installer/package remain pending.

Next phase: `P2C.5C.4 REAL BROWSER ACCEPTANCE + RECOVERY UX`. It is not started
by this implementation phase.
