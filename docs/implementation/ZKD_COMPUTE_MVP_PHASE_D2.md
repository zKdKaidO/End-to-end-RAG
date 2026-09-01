# ZKD Compute MVP — Phase D2

## Scope

P2C.4D.2 adds explicit generation routing beneath the completed local
Blocks 4–6 path. It does not modify the frozen architecture contracts,
frontend, retrieval, hierarchy, Block 5 semantics, canonical `legal-rag-v2`
prompt construction, or canonical answerability/citation finalization.

## Economic invariant

Active V1 has exactly two executable provider types:

- `LOCAL`: the user's ZKD Compute device and its own Ollama/runtime.
- `USER_CLOUD`: an endpoint, account, and credential explicitly owned by the
  user.

`PLATFORM_CLOUD` is represented only as a disabled identity. It has no
provider implementation, endpoint, credential, fallback, or API-key path.
The router rejects it with `PLATFORM_CLOUD_DISABLED`. No policy can select it.
The default is conservative `LOCAL_ONLY`; therefore local model loss cannot
spend money on a platform or user-cloud provider without an explicit,
preconfigured routing request.

## Provider/configuration model

`UserCloudProviderConfig` contains a stable UUID `provider_config_id`,
transport (`OPENAI_COMPATIBLE` for the one V1 reference adapter), endpoint,
model ID, credential reference, and enabled state. Its serialized metadata
excludes both endpoint and credential reference; it never contains a secret.
Configuration lives in an internal local-runtime registry. There is no
browser configuration/CRUD protocol route and answer requests can name only
an existing `provider_config_id`, never an arbitrary URL.

The reference adapter translates the identical canonical Block 6 message list
to OpenAI-compatible `/models/{model}` health and `/chat/completions` wire
requests. It sends only the selected canonical prompt/evidence context needed
for the requested answer, bounded output and canonical timeout. It sends no
PDF bytes, local artifacts, vectors, platform relay payload, or provider
metadata supplied by the remote response.

## Credential and network boundary

Production defaults to `UnavailableUserCloudCredentialStore`. A production
runtime cannot configure or execute user cloud until a secure OS-protected
credential-store implementation is supplied; it fails closed with
`CREDENTIAL_STORE_UNAVAILABLE`. The in-memory store is explicitly restricted
to development/test runtime and is never written to SQLite, manifest metadata,
logs, or responses.

HTTPS is required in production. Development/test may use literal loopback
HTTP only for an isolated fake provider. Unsafe schemes, URL credentials,
query/fragment endpoint forms, and arbitrary request-time URLs are rejected.
The adapter can reach only its already-configured endpoint and exposes no
generic fetch/proxy operation. Errors are typed and sanitized; provider error
bodies, Authorization headers, bearer values, and secrets are never surfaced
or logged.

Privacy differs by selection and is returned in safe routing metadata:

- `LOCAL_DEVICE`: query/context/evidence remain in local compute.
- `USER_CLOUD_EXTERNAL`: canonical generation input leaves the device directly
  for the explicitly configured user-owned endpoint. It never traverses ZKD
  platform, analytics, or a platform relay.

## Routing and fallback

`GenerationRoutingPolicy` supports `LOCAL_ONLY`, `USER_CLOUD_ONLY`,
`PREFER_LOCAL`, and `PREFER_USER_CLOUD`.

| Policy | Primary | Fallback |
|---|---|---|
| `LOCAL_ONLY` | local | never external |
| `USER_CLOUD_ONLY` | configured user cloud | never local unless another explicit policy is selected |
| `PREFER_LOCAL` | local | user cloud only when `allow_user_cloud_fallback=true` |
| `PREFER_USER_CLOUD` | configured user cloud | local only when `allow_local_fallback=true` |

Routing occurs after retrieval, hierarchy expansion, Block 5 context building,
canonical prompt assembly, and prompt-budget validation. It performs no
automatic semantic retry. A generation failure does not switch providers.
Routing metadata records policy, selected type/config ID, whether a permitted
fallback occurred, and privacy boundary—never prompt/query/context/secret.

`POST /v1/answers` remains backward compatible: absent routing fields use
`LOCAL_ONLY`. It returns provider type, configured model identity, optional
provider config ID, and safe routing metadata. `POST /v1/queries` remains
retrieval-only and cannot access generation routing.

## Block 6 normalization and capability reporting

Both providers return an internal `LLMResult`; the local finalizer applies the
same status parser, exact `[Sx]` citation parser, selected-evidence mapping,
unknown-citation behavior, provenance mapping, and public structured result.
The user-cloud model ID is returned as its configured identity, while the
prompt profile remains `legal-rag-v2`.

Capability reporting retains the local capability independently and adds a
routing report: default `LOCAL_ONLY`, local live state, user cloud
`NOT_CONFIGURED` when absent, and platform cloud `DISABLED`. User-cloud
availability can be `READY`, `NOT_CONFIGURED`, `CREDENTIAL_UNAVAILABLE`,
`UNREACHABLE`, `AUTH_FAILED`, `RATE_LIMITED`, `MODEL_UNAVAILABLE`, or
`DEGRADED`; configuration alone is not treated as ready.

## Verification

Deterministic isolated tests cover all policies, explicit fallback permissions,
platform disable, production credential-store fail-closed behavior, endpoint
validation, secret redaction, successful/401/429/5xx/timeout/malformed
OpenAI-compatible fake-provider behavior, canonical Block 6 parity, and
retrieval-only non-interference. No real external provider or credential was
used: `USER_CLOUD_REAL_PROVIDER_NOT_EXECUTED`.

Focused existing local suites continue to cover real E5 local retrieval,
hierarchy expansion, Block 5 context compatibility, and opt-in real local
`qwen3.5:9b` generation. Browser acceptance remains
`BROWSER_ACCEPTANCE_NOT_EXECUTABLE`; no browser security setting was altered.

## Known limitations and next phase

There is no OS credential-manager integration, frontend provider UI,
production browser integration, streaming cancellation, provider marketplace,
billing, platform-paid inference, or real external-provider acceptance in D2.
The next phase is `P2C.5 ZKD COMPUTE PRODUCT INTEGRATION FOUNDATION`, split
into provider/device runtime discovery, browser/local session integration,
manifest/local availability integration, `/ask` product orchestration, and
`/documents` local-state integration. It must not begin from this phase.
