# ZKD Compute Product Phase 5C.3A — Local Ask Product Contract Completion

## Scope and result

This is a non-visual contract-completion phase for the later human-owned Ask
page wiring. It does not change `AskPage`, any visual/CSS files, Blocks 1–6,
retrieval semantics, hierarchy expansion, context construction, `legal-rag-v2`,
or the local runtime protocol routes.

The result is `ASK_LOCAL_FIRST_CONTRACT_PARTIAL`: the normal local-first Ask
flow is ready to wire without inventing retrieval or generation semantics, but
the legacy streaming, backend cancellation, persistent history, and full
evidence-drawer UX must be downgraded or deferred in the next page phase.

## Baseline and inherited worktree

- Baseline HEAD: `5745a65daf7513326524a6384ddb0963e99989b7`
  (`feat: complete local document lifecycle`).
- The existing uncommitted Documents local-first integration in
  `frontend/src/pages/DocumentsPage.tsx` and its test was preserved exactly.
  Its accompanying untracked implementation record also remained untouched.
- The baseline and final frontend build both report exactly the same three
  pre-existing `SourcePanel.tsx` TypeScript errors for `citation_label`,
  `snippet`, and `content_preview`. This phase introduces no new build error.

## Current Ask audit and platform-content paths

The current working-tree `AskPage` is still platform-chat based. It loads
`api.documents()` and `api.status()` on mount; creates, lists, renames, deletes,
and reads platform chat sessions through `api.createChatSession`,
`api.chatSessions`, `api.renameChatSession`, `api.deleteChatSession`, and
`api.chatMessages`; streams a turn through `streamChatTurn`; and gives
`SourceDrawer` a citation that can cause `api.chunk(chunkId)` to retrieve
evidence through the platform.

| Current Ask action | Current call | Content exposed to platform | Local-first P2C.5C.3B replacement |
| --- | --- | --- | --- |
| source list | `api.documents()` | document metadata and canonical IDs | `compute.listDocuments()` from the selected device |
| send / answer | `streamChatTurn(...)` | question, source scope, answer, evidence/citations | one `compute.answer(...)` request |
| new, recent, load older | chat session/message APIs | questions, answers, citations, titles, scope/turn metadata | browser-memory current-page transcript only |
| rename/delete history | chat session APIs | query-derived title and history | deferred; do not persist content on platform |
| citation drawer | `api.chunk(...)` if no historical snapshot | chunk text/evidence | metadata/provenance-only local citation view, or a later local evidence route |
| retry | finds platform history then streams platform turn | historical question and scope | resubmit the browser-memory user turn with a fresh local request |

After the page migration, the platform may handle authenticated device discovery,
metadata-only manifests, and grant issuance only. It must not receive the query,
retrieved chunk text, context, prompt, generated answer, or citation/evidence
text. There is no platform fallback when local Compute is offline.

## Local query contract

`BrowserComputeClient.query(request)` now has a typed result and sends an
authenticated `POST /v1/queries` to the selected literal loopback endpoint.

```ts
{ query_text: string, document_ids?: string[] | null }
```

The local route performs provider-independent canonical local Block 4 work:
E5 query embedding, dense + FTS5 lexical candidates, RRF (`50/50/10`, `k=60`),
and the existing hierarchy expansion. It returns:

```ts
{ request_id, results: LocalRetrievedCandidate[], hierarchy }
```

Each result contains local `chunk_id`, `document_id`, artifact/legal-unit IDs,
content text, metadata/provenance, dense/lexical/RRF ranks and signals, and
hierarchy fields. There is no caller-selectable top-k and no provider choice.

Frozen local-store behavior is `document_ids is None or [] -> all INDEX_READY
documents`. Explicit IDs are device-local and only query that exact list. A
browser product state of zero selected sources must never send `[]`, because it
would broaden the request. The browser client now rejects it locally with
`EMPTY_DOCUMENT_SCOPE`; “all selected” must be represented by omitting the
field or passing `null`.

## Local answer contract and canonical flow

`BrowserComputeClient.answer(request)` is typed and sends an authenticated,
non-streaming `POST /v1/answers`:

```ts
{
  query_text: string,
  document_ids?: string[] | null,
  routing_policy?: "LOCAL_ONLY" | "USER_CLOUD_ONLY" |
                    "PREFER_LOCAL" | "PREFER_USER_CLOUD",
  provider_config_id?: string,
  allow_user_cloud_fallback?: boolean,
  allow_local_fallback?: boolean
}
```

The route rejects browser-supplied provider endpoints and credentials. It runs
local retrieval once, builds the canonical Block 5 context, assembles
`legal-rag-v2`, resolves the configured local/user-cloud provider locally, and
uses canonical Block 6 finalization. The normal Ask product flow is therefore
**answer only**. Calling `query` before `answer` would duplicate retrieval and
must be limited to diagnostics or an explicit future evidence UX.

The typed response is:

```ts
{
  request_id, provider: "LOCAL" | "USER_CLOUD", provider_type,
  provider_config_id, model_id,
  result: {
    request_id, status, answer_text, citations, invalid_citations,
    citation_validation, model_id, prompt_version, finish_reason, usage,
    answerability_status, answerability_validation
  },
  hierarchy,
  timings: { retrieval_ms, context_build_ms, prompt_token_count,
             generation_ms, total_ms, time_to_first_token_ms: null },
  routing
}
```

No status is inferred from answer text. Typed local errors remain signed local
HTTP failures and are exposed by the browser client as safe typed client errors.

## Scope, citations, and source inspection

The current visual selection rules map cleanly when its source list comes from
the same selected device:

- all local sources selected: `document_ids: null` or omitted;
- explicit non-empty subset: exact device-local IDs;
- zero selected when sources exist: submit disabled and client guard rejects
  accidental requests.

Canonical answer text retains the exact `[S1]`, `[S2]`, … markers. Citation
objects bind those source IDs to `chunk_id`, `document_id`, `metadata_json`, and
`provenance_json`; citation numbering must not be re-written by the browser.

| Field | Local answer citation | Current SourcePanel expectation | P2C.5C.3B treatment |
| --- | --- | --- | --- |
| source label | `source_id` (`S1`) | `citation_label` | mappable semantically, not the same field |
| chunk/document IDs | present | indirectly used | available |
| metadata/provenance | present | usable only through other current types | available, safe to show locally |
| evidence snapshot | absent | `snippet` / `content_preview` | missing; do not fabricate |
| historical availability | absent | `CURRENT_EQUIVALENT`, `SOURCE_UPDATED`, `SOURCE_UNAVAILABLE` | unsupported for device-local V1 |

`SourcePanel` is not merely stale TypeScript usage: its `citation_label` is
mappable to `source_id`, but `snippet` and `content_preview` are not supplied by
either the local answer or citation contract. Separately, the current
`SourceDrawer` calls platform `api.chunk` when a citation lacks a stored
snapshot, which violates local-first privacy. P2C.5C.3B must not retain that
lookup. It may use a metadata/provenance-only local citation drawer, or a later
narrow local evidence endpoint can supply full content. Historical platform
citation availability states must not be transplanted to local documents.

## Provider, streaming, and cancellation

The local router supports `LOCAL` and an explicitly configured `USER_CLOUD`
provider. `PLATFORM_CLOUD` is disabled and has no fallback route. A UserCloud
request carries only routing identity to local Compute; its configuration and
credential remain on the device, and the selected context may leave only by the
explicit user-funded direct provider path. ZKD is not a relay.

Current local `/v1/answers` is synchronous JSON only. It has no SSE, WebSocket,
answer job, polling model, TTFT, or request-specific cancellation. The existing
`/v1/jobs/{id}:cancel` applies to durable document jobs, not answers. The local
provider's cancellation boundary returns `False`; a browser abort can stop
awaiting a response but cannot truthfully claim the model stopped.

`LOCAL_ANSWER_CANCEL_GAP` is therefore recorded. P2C.5C.3B may preserve a
pending/non-streaming shell and a truthful local failure state, but must not
surface the old streaming deltas or label browser abort as completed backend
cancellation. A later cancellation design needs a request identity, an
authoritative local lifecycle, and provider-safe cancellation before a Stop
control can make that claim.

## History, retry, device, and outage behavior

No local Compute conversation/history API or store exists. The smallest
architecture-correct V1 is a browser-memory-only transcript for the current
page lifecycle: New clears it; reload/navigation loses it; no query-derived
title, answer, citation, or source scope is persisted to platform or
`localStorage`. Rename, delete, recent conversations, and older-history are
deferred UX rather than platform fallbacks.

Retry creates a new local `answer` call from the retained browser-memory user
turn and current valid scope. The client serializes fresh bytes and applies a
fresh timestamp, nonce, and MAC. It must not automatically replay an ambiguous
generation request after a loopback failure.

Existing valid local browser sessions can query or answer while the platform is
unavailable; no per-request platform preflight occurs. An expired/missing
session needs a new platform grant. A device-offline error remains local and
must not trigger platform retrieval/generation. The app currently has no
app-wide device selector: exactly one usable `READY` device may be selected;
multiple devices yield `DEVICE_SELECTION_REQUIRED`. Device-local document IDs
are not portable to another device. Switching clients/devices clears the local
session, and the future Ask page must reload its source list before accepting
scope for the newly selected device.

Documents currently owns a page-scoped client. A second Ask page-scoped client
would produce another discovery/grant/session when navigating. P2C.5C.3B should
use one app-scoped, in-memory-only client (for example an eventual context) if
the visual/application owner can introduce it safely. It must expose only the
redacted snapshot and never persist the session key. If that cannot be added in
the page-only change, a page-scoped Ask client remains correct but less
efficient and must re-read the selected device's catalog.

## P2C.5C.3B state model and migration map

The non-visual state contract is:

```ts
type LocalAskTurn = {
  userText: string;
  documentIds: string[] | null;
  state: "pending" | "completed" | "failed";
  answer?: LocalGenerationResult;
  provider?: "LOCAL" | "USER_CLOUD";
  error?: BrowserComputeError;
};
```

`cancelled` is not a truthful local terminal state until the local runtime adds
authoritative answer cancellation.

| Current behavior | Local-first replacement | Status |
| --- | --- | --- |
| source loading | `compute.listDocuments()` from selected device | READY |
| all/subset selection | local IDs; null/omitted for all; reject zero | READY |
| submit | one `compute.answer()` | READY |
| query then answer | answer only; query only for diagnostics | READY |
| provider | default LOCAL; optional configured USER_CLOUD routing only | ADAPT IN UI |
| streaming | wait for synchronous local JSON result | ADAPT IN UI |
| Stop | no truthful answer cancellation | BACKEND GAP |
| retry | fresh browser-memory local answer request | ADAPT IN UI |
| inline citations | preserve answer `[Sx]`, bind local citations | READY |
| source inspection | metadata/provenance locally; no platform `api.chunk` | ADAPT IN UI |
| source preview/full text | requires a future local evidence endpoint | DEFERRED UX |
| recent history/session route | browser-memory transcript only | ADAPT IN UI |
| reload history | intentionally lost | UNSUPPORTED V1 |
| new/rename/delete chat | New clears memory; rename/delete deferred | DEFERRED UX |
| local offline | typed unavailable state, no platform fallback | READY |
| platform outage | existing local session continues | READY |
| multiple devices | require one or surface ambiguity | ADAPT IN UI |

## Browser-client and runtime changes

This phase makes no `app/local_compute/*` change. It adds only the following
browser contract completion:

- typed local query candidates/results, answer request/response, citations,
  status, routing, and safe timing types;
- typed `BrowserComputeClient.query` and `.answer` methods;
- `EMPTY_DOCUMENT_SCOPE` and early scope validation, before discovery, grant, or
  a local request.

The guard preserves the backend's frozen `[] -> all queryable` semantics while
making zero selection product-invalid in the browser. It does not alter any
retrieval or generation behavior.

## Verification

- `frontend/src/compute/client.test.ts`: 15 passing browser tests, including
  query/answer after one local bootstrap with zero platform content calls,
  exact explicit-scope bytes, zero-scope rejection, platform-outage local
  answer continuation, and expiry rebootstrap.
- Combined client and preserved Documents tests: 23 passed.
- Local focused suites in the API container: 30 passed, 1 intentionally skipped
  without the opt-in model flag, 7 existing warnings. They cover local query,
  local answer/finalization/citations, explicit user-cloud routing with no
  browser credential endpoint, platform-cloud rejection, signed operation
  admission, platform outage/revocation, and device/session binding.
- Follow-up lifecycle/control/provider run: 22 passed, 7 existing warnings.
- The lifecycle test explicitly records the actual omitted/null/empty local
  retrieval behavior and the browser-only zero-scope protection.
- Real opt-in authenticated local generation:
  `RUN_LOCAL_GENERATION_E2E=1 ... test_generation_e2e.py` — 1 passed. It used a
  temporary Compute root, the natural `qwen3.5:9b` model at digest
  `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`, and
  validated non-empty canonical output with source-bound citations.
- Frontend build after changes: still fails only the three pre-existing
  `SourcePanel.tsx` fields above.

Real Chrome/Edge PNA/CORS acceptance and a packaged OS credential store remain
outside this phase.

## Next phase

`P2C.5C.3B ASK LOCAL-FIRST PAGE WIRING` may start as a data-wiring change only.
It must retain the existing visual files' ownership while replacing their
platform content calls with this contract and documenting the listed UX
deferments. It must not start automatically from this phase.
