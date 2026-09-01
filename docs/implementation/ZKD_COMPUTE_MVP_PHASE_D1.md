# ZKD Compute MVP — Phase D.1

## Scope

Phase D.1 adds only the first executable local generation path to the
standalone ZKD Compute service.  It preserves the cloud application’s Block 6
semantics and does not change production provider selection, frontend code,
database schema, retrieval, hierarchy, context construction, or the frozen
architecture contracts.

The local path is:

```text
LocalRetrievalStore -> DIRECT_CHILD -> ContextBuilderService
  -> legal-rag-v2 prompt -> LocalGenerationProvider
  -> canonical status/citation finalization -> local structured answer
```

## Canonical Block 6 compatibility

The existing `legal-rag-v2` system prompt, deterministic Block 5 context,
Qwen tokenizer/chat template, 4096-token context budget, 512-token output
limit, prompt budget guard, answerability marker parser, and citation parser
remain authoritative.

The pure Block 6 finalization logic now lives in
`app.generation.finalization.finalize_generation_result` and is used by both
the unchanged production `AnswerService` and the local service.  This is a
behavior-preserving extraction: `ANSWERABLE`/`INSUFFICIENT_EVIDENCE`, the
standard insufficient-evidence message, exact `[S1]` citation syntax,
invalid-reference warnings, missing-citation warnings, provenance mapping,
and no-status warning behavior are unchanged.

## Provider boundary and economic invariant

`GenerationProviderType` explicitly defines `LOCAL`, `USER_CLOUD`, and
`PLATFORM_CLOUD`.  Only `LOCAL` is executable in D.1.

`LocalGenerationProvider` wraps the canonical Ollama message/payload contract
behind a local-only boundary.  It reports availability, model identity,
generates using the configured canonical profile, and exposes an honest
non-streaming cancellation result (`False`).  Ollama has no safe
request-specific cancellation operation through this non-streaming API; an
HTTP request may stop awaiting a result, but D.1 does not claim that it kills
the underlying model work.

`GenerationRouter` selects only `LOCAL`.  It rejects `USER_CLOUD` and
`PLATFORM_CLOUD` as `CAPABILITY_UNAVAILABLE`; there is no cloud fallback,
provider retry, API key, billing path, or platform-paid inference.  A missing,
loading, unavailable, or timed-out local model fails with a typed local error.

The packaged default endpoint is literal loopback `http://127.0.0.1:11434`.
The Docker Desktop host gateway is accepted only when explicit development
mode is enabled so this repository can run isolated acceptance against the
same host’s locally installed Ollama process.  Arbitrary remote endpoints are
rejected.

## Local orchestration and protocol

`LocalAnswerService` owns local answer orchestration.  It validates the
opaque document scope, calls local retrieval/hierarchy, passes only validated
local evidence through the C.3 Block 5 adapter, builds the canonical prompt,
enforces the canonical prompt budget, calls the local provider, and returns a
structured local response:

```text
provider, model_id, GenerationResult, hierarchy diagnostics, safe timings
```

It has no PostgreSQL, Redis/RQ, MinIO, platform API, or cloud-provider client.
`POST /v1/queries` remains the authenticated retrieval-only evidence endpoint.
`POST /v1/answers` is an additive authenticated local `answer_document_set`
operation; it never relays content through the platform backend.

Capability reporting now declares the implemented local PDF-through-retrieval
substrate as `READY` and independently checks generation-model availability.
Generation may be `READY`, `MODEL_UNAVAILABLE`, or `DEGRADED` without making
retrieval unavailable.

## Structured answers, citations, and privacy

The local response exposes no chain-of-thought.  It contains only
product-facing answer text, generation status, source-bound citations,
invalid citation IDs where canonical Block 6 reports them, provider/model
identity, and safe timing/token metadata.  A citation resolves only through
the selected Block 5 evidence list, preserving local document/chunk metadata
and provenance.  Unknown source IDs remain canonical warning results and are
never silently mapped to a local artifact.

Logging records request ID, local provider type/model, counts, status, and
duration.  It does not log raw query, context, evidence, prompt, answer,
session key, or endpoint path.  The real acceptance used the host’s installed
local Ollama through Docker’s development-only host gateway; no paid cloud
provider or platform service was invoked.

## Validation

Focused tests cover local provider availability, unavailable models, timeout,
strict endpoint admission, cancellation boundary, local-only routing,
platform-cloud rejection, canonical prompt/finalization, source mapping,
unknown citations, malformed status, no-fallback behavior, and capability
reporting.  Existing C.3 retrieval/hierarchy/context and canonical Block 4–6
tests remain green.

The opt-in real E2E test uses a text-native Unicode legal PDF, real canonical
E5 indexing, local dense/FTS5/RRF/direct-child retrieval, canonical Block 5,
the real `qwen3.5:9b` local model, and canonical citation finalization.  It
returned a non-empty locally generated answer with a valid source-bound
citation.  Observed warm-run metrics: 179 context tokens, 588 model-facing
prompt tokens, 22 output tokens, and approximately 0.62 seconds total local
answer orchestration; synchronous non-streaming generation does not expose
TTFT.

## Known limitations and next phase

This is a local-service foundation, not browser/desktop production
integration.  Browser acceptance remains `BROWSER_ACCEPTANCE_NOT_EXECUTABLE`.
There is no streaming local answer protocol, request-specific model
cancellation, installer/model lifecycle UX, or user-funded cloud provider.
Normal users must not be asked to operate Ollama or any developer tool; later
ZKD Compute packaging owns that lifecycle.

Next: `P2C.4D.2 USER-FUNDED GENERATION PROVIDER + ROUTING POLICY`.
