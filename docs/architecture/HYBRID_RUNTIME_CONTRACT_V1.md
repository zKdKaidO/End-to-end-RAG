# HYBRID_RUNTIME_CONTRACT_V1

**Project:** ZKD / Legal RAG Hybrid End-User Compute  
**Status:** **FROZEN V1**  
**Scope:** Cloud ↔ End-User Device runtime contract for optional local generation  
**Public application:** `https://rag.zkd.id.vn`  
**Protocol philosophy:** Transport-neutral, vendor-neutral, security-first, cloud-canonical  
**Last updated:** 2026-08-31

---

## 0. Executive Summary

ZKD is a cloud-first, multi-user Legal RAG application that remains usable even when no end-user compute device is online.

The cloud owns canonical state, security, retrieval, orchestration, and product availability. An end user's computer may optionally act as a personal compute accelerator through **ZKD Compute**.

In V1, the only workload offloaded to an end-user device is **LLM generation**.

```text
                       https://rag.zkd.id.vn
                                │
                                ▼
                         CLOUDFLARE EDGE
                      DNS / TLS / WAF / CDN
                                │
                                ▼
                ┌──────────────────────────────┐
                │ ALWAYS-ONLINE CONTROL PLANE │
                │                              │
                │ Frontend                     │
                │ API / Auth                   │
                │ PostgreSQL + pgvector        │
                │ Object Storage               │
                │ E5 / Retrieval               │
                │ Context Construction         │
                │ Citation Validation          │
                │ Device Registry              │
                │ Compute Router               │
                │ Job Orchestration            │
                └──────────────┬───────────────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
                  ▼                         ▼
          USER'S OWN DEVICE             CLOUD LLM
           ZKD Compute                  Provider
           CPU / GPU                    Fallback
                  │                         │
                  └────────────┬────────────┘
                               ▼
                         Streaming Result
                               │
                               ▼
                            Browser
```

The user never needs Docker, Python, pip, Git, CUDA Toolkit installation instructions, or terminal commands to use ZKD Compute.

---

# 1. Frozen Architectural Invariants

The following rules are **FROZEN for V1**.

## 1.1 Cloud is always available and owns canonical truth

Canonical data remains in the cloud:

- user identity and authentication;
- authorization;
- original document metadata;
- source documents / canonical object references;
- document lifecycle;
- legal chunking results;
- embeddings and retrieval indexes;
- chat/session history;
- evidence/citation state;
- device registry;
- job state;
- audit/provenance.

A user device is not a source of truth.

## 1.2 Local devices are optional and untrusted compute

```text
LOCAL DEVICE
= compute accelerator

LOCAL DEVICE
≠ security authority
≠ canonical database
≠ trusted source of truth
```

## 1.3 Generation is the only local workload in V1

V1 supports only `GENERATE` on end-user devices. Ingestion, parsing, chunking, canonical embedding/indexing, retrieval, context construction, citation validation, auth, authorization, billing/quota, and audit logging stay cloud-side.

## 1.4 A user's request may only use that user's own device

```text
User A → Device A
User B → Device B
```

Cross-user compute pools are outside V1.

## 1.5 Cloud fallback requires explicit consent

Consent levels:

- `ONE_TIME`: cloud may be used for this generation only.
- `PERSISTENT`: cloud may automatically be used when the user's local device is unavailable.

Without consent, cloud fallback must not occur silently.

## 1.6 No mixing Local + Cloud inside one generation

If local generation has emitted user-visible content and then fails, cloud must not continue the same answer. Cloud retry begins from the start as a **new generation run**.

## 1.7 No Docker or developer tooling for end users

ZKD Compute must not require manual Docker, Python, pip, Conda, Git, source builds, terminal commands, or project repositories.

## 1.8 No arbitrary remote code execution

Forbidden protocol operations include `RUN_SHELL`, `EXEC`, `POWERSHELL`, `CMD`, `RUN_ARBITRARY_BINARY`, and `INSTALL_ARBITRARY_PACKAGE`.

## 1.9 Protocol is frozen independently from transport/vendors

The protocol remains valid whether implemented with WebSocket, WebTransport, another bidirectional transport, FastAPI, a dedicated gateway, Redis Streams, NATS, or another durable broker.

---

# 2. Control Plane and Data Plane Boundary

## 2.1 Cloud Control Plane

Cloud owns frontend, API, authentication, authorization, PostgreSQL, pgvector, object storage, durable job state, E5 query embedding, hybrid retrieval, context construction, citation validation, device registry, compute router, orchestration, cloud-provider integration, and audit/provenance.

## 2.2 End-User Compute Plane

```text
ZKD Compute
│
├── Desktop UI
├── Device Agent
├── Capability Detector
├── Runtime Manager
├── Model Manager
├── Benchmark Engine
├── Generation Worker
└── Secure Cloud Client
```

Concrete desktop framework and inference engine are not frozen.

---

# 3. Device Identity Contract

Required logical fields:

```text
user_id
device_id
device_name
agent_version
protocol_version
installation_id
credential_id
created_at
```

A device belongs to exactly one user account in Personal Compute V1. Cloud authorization must validate `job.user_id == device.owner_user_id` before dispatch.

Device authentication must use a revocable per-device credential stored using OS-protected credential storage where available. A user password must never be stored by the agent.

---

# 4. Device Pairing Contract

Recommended logical flow:

```text
Website (authenticated user)
   │
   └── create short-lived one-time pairing request
                     │
                     ▼
                ZKD Compute
                     │
                confirms device
                     │
                     ▼
Cloud issues revocable per-device credential
```

Pairing codes/tokens must be short-lived, one-time use, user-bound, and invalid after success. Exact UX/transport are not frozen.

---

# 5. Device Lifecycle State Machine

Frozen states:

```text
OFFLINE
CONNECTING
AUTHENTICATING
IDLE
READY
BUSY
UNAVAILABLE
DRAINING
```

Conceptual transitions:

```text
OFFLINE
   │
   ▼
CONNECTING
   │
   ▼
AUTHENTICATING
   │
   ▼
IDLE
   │ runtime/model/resource validation
   ▼
READY
   │
   ├── job accepted ─────────► BUSY ── complete/fail ──► READY
   ├── resource pressure ────► UNAVAILABLE ─ recovered ─► READY
   └── shutdown/update ──────► DRAINING ───────────────► OFFLINE
```

Connectivity alone never implies `READY`.

---

# 6. Capability Contract

## 6.1 Static capability

Examples: OS, architecture, CPU, logical cores, RAM, GPU vendor/model, total VRAM, driver, supported backends, disk, installed runtime profiles, installed model profiles.

## 6.2 Dynamic availability

Examples: free VRAM, free RAM, GPU load, memory pressure, model loaded state, runtime health, battery state, thermal/resource pressure, queue depth, user pause state.

Router eligibility is:

```text
Static Capability + Dynamic Availability + Job Requirements
```

Hardware model name alone never implies readiness.

---

# 7. Job-Time Resource Admission

Before every generation job, the device must re-check dynamic resources. Typed rejection reasons include:

```text
DEVICE_BUSY
INSUFFICIENT_VRAM
INSUFFICIENT_RAM
MODEL_NOT_READY
RUNTIME_UNHEALTHY
USER_PAUSED
BATTERY_POLICY
RESOURCE_PRESSURE
INCOMPATIBLE_PROFILE
```

This is required to handle VRAM contention from games, renderers, other AI workloads, and OS pressure.

---

# 8. Runtime and Model Manifest Contract

Cloud publishes approved versioned manifests. Logical shape:

```yaml
generation_profile: qwen-local-balanced-v1

runtime_profile:
  id: zkd-runtime-profile-v1
  version: '<version>'

model:
  id: '<model-id>'
  version: '<model-version>'
  quantization: '<profile>'
  size_bytes: <integer>
  sha256: '<digest>'

requirements:
  minimum_ram_bytes: <integer>
  minimum_vram_bytes: <integer>
  supported_backends:
    - '<backend>'
  minimum_driver: '<optional-version>'

protocol:
  minimum_agent_version: '<version>'
```

Exact model/runtime values are not frozen. Agent may report only profiles it can actually execute.

---

# 9. Runtime and Model Distribution Contract

The installer must not bundle large model weights by default. Required lifecycle:

```text
manifest
   ↓
resumable download to temporary location
   ↓
size verification
   ↓
cryptographic hash/signature verification
   ↓
atomic activation
```

Interrupted downloads may resume; corrupted/partial artifacts are never activated; failed updates preserve the previous working runtime/model; users may remove models; storage quota is enforceable.

---

# 10. Driver Boundary

ZKD Compute may detect incompatible drivers but must not silently install or upgrade system-level GPU drivers in V1. The UI must explain current state, required capability, why it matters, official vendor source, and the option to use cloud instead.

---

# 11. Compute Job Contract

V1 supports one job type: `GENERATE`.

Logical request fields:

```text
job_id
attempt_id
generation_run_id
user_id
device_id
generation_profile
trace_id
created_at
deadline_at
generation_parameters
prompt_context_payload
payload_hash
```

Device must return either `JOB_ACCEPTED` or `JOB_REJECTED` with a typed reason.

---

# 12. Protocol Envelope

Every message uses a common logical envelope:

```text
protocol_version
message_type
message_id
session_id
connection_epoch
device_id
sent_at
trace_id
job_id       # nullable for non-job messages
attempt_id   # nullable for non-job messages
sequence     # required for ordered job events
payload
```

Serialization format is not frozen.

---

# 13. Idempotency and Duplicate Delivery

Reconnects/retries may duplicate messages. Therefore:

- `message_id` is unique;
- `job_id + attempt_id` identifies one compute attempt;
- device must not execute the same accepted attempt twice;
- cloud tolerates duplicate events;
- terminal job events are idempotent.

A redelivered `RUN_GENERATION` must report/resume the existing attempt or report its terminal state, never start an independent duplicate generation.

---

# 14. Connection Epoch and Stale Session Protection

Every authenticated connection receives a `connection_epoch`. A newer connection supersedes the previous epoch. Stale-epoch messages may not overwrite device state, claim jobs, complete newer attempts, or mark a newer session READY.

---

# 15. Streaming Event Contract

Frozen logical events:

```text
JOB_ACCEPTED
GENERATION_STARTED
TEXT_DELTA
GENERATION_COMPLETED
GENERATION_FAILED
JOB_CANCELLED
```

Frontend continues to call the existing answer-stream API and does not need to know whether output came from local or cloud.

---

# 16. Ordered Delivery

`TEXT_DELTA` events use monotonically increasing `sequence` numbers per `attempt_id`. Cloud ignores exact duplicates, detects gaps, and never silently reorders generated content. Unlimited replay is not required in V1.

---

# 17. Reconnection Storm Protection

**FROZEN RULE:** `OFFLINE → CONNECTING` must use **Exponential Backoff + Random Jitter**.

Required behavior:

- retry delay grows after repeated failures;
- delay is capped;
- jitter spreads retries across devices;
- stable successful connection resets backoff;
- server retry guidance is honored within safe bounds.

Exact constants/distribution are configurable, not frozen.

---

# 18. Payload Size Contract

V1 application-level limits:

```text
Maximum logical RUN_GENERATION message: 128 KiB UTF-8 serialized payload
Maximum logical TEXT_DELTA message:      16 KiB UTF-8 serialized payload
```

These limits are independent of transport frame limits.

If a generation request exceeds the limit:

```text
DO NOT DISPATCH
DO NOT RELY ON TRANSPORT FRAGMENTATION
DO NOT SILENTLY TRUNCATE
```

The orchestrator must fail admission with `PAYLOAD_TOO_LARGE` and either rebuild a smaller deterministic context or return a controlled failure. Protocol-level compression and multi-message request fragmentation are not required in V1.

---

# 19. Generation Watchdog and Zombie Job Prevention

**FROZEN RULE:** heartbeat health and generation progress are separate. Every generation attempt has independent watchdogs:

```text
ACCEPT_TIMEOUT
START_TIMEOUT
FIRST_DELTA_TIMEOUT
DELTA_INACTIVITY_TIMEOUT
OVERALL_DEADLINE
CANCEL_TIMEOUT
```

Exact timeout values are server-configurable and not frozen.

If progress stops beyond the configured watchdog, cloud records:

```text
GENERATION_FAILED
reason = DEVICE_TIMEOUT
```

and the browser stream must terminate rather than hang forever.

Before first user-visible delta, cloud may start a new attempt only if consent allows. After any user-visible delta, the current answer is interrupted and cloud retry starts from the beginning as a new run.

---

# 20. Heartbeat Contract

Heartbeat carries control state only:

```text
device_id
connection_epoch
device_state
runtime_health
resource_snapshot
queue_depth
active_job_id
timestamp
```

It must not carry documents, prompts, context, or token streams. Frequency/offline thresholds remain configurable.

---

# 21. Router Policy Contract

Frozen internal policies:

```text
LOCAL_ONLY
CLOUD_ONLY
PREFER_LOCAL
PREFER_CLOUD
```

Suggested user-facing labels are simpler and are not frozen.

---

# 22. Local Selection Logic

A local device is eligible only if ownership is valid, device authenticated, protocol compatible, state READY, profile supported, runtime healthy, model ready, resources sufficient, user policy permits local, and concurrency policy allows a job. Router records typed non-selection reasons.

---

# 23. Cloud Fallback Consent Contract

Logical consent states:

```text
NONE
ONE_TIME
PERSISTENT
```

Each cloud fallback records the consent that authorized it. Persistent consent is revocable.

---

# 24. Failure Matrix

| Failure | Tokens shown? | Allowed behavior |
|---|---:|---|
| Device unavailable before dispatch | No | Ask user or use cloud if consent exists |
| Device rejects job | No | Ask user or cloud fallback if consent exists |
| Device disconnects before first delta | No | New cloud attempt allowed if consent exists |
| Device disconnects after first delta | Yes | Stop; offer **Regenerate with Cloud** |
| Local runtime crash before first delta | No | New cloud attempt if consent exists |
| Local runtime crash after first delta | Yes | Stop; never splice providers |
| Cloud provider fails before first delta | No | Local retry may be offered if READY |
| Cloud provider fails after first delta | Yes | Stop; new generation required |
| Both providers unavailable | No | Typed generation-unavailable response |
| Browser cancels | Any | Cancel active provider attempt |
| Job watchdog expires | Depends | `DEVICE_TIMEOUT`; apply pre/post-delta rules |

---

# 25. Cancellation Contract

Browser Stop propagates `Browser → Cloud API → CANCEL_JOB → Active Provider`. Device attempts to stop inference, stop deltas, release generation resources, and return `JOB_CANCELLED`. UI stopping while GPU continues indefinitely is a contract violation.

---

# 26. Cloud Provider Contract

Cloud generation implements the same logical event contract as local generation behind a `GenerationProvider` abstraction:

```text
LocalDeviceProvider
CloudGenerationProvider
```

Exact cloud vendor/model is not frozen.

---

# 27. Generation Provenance Contract

Each run persists at least:

```text
generation_run_id
provider_type          # LOCAL_DEVICE / CLOUD
device_id              # nullable for cloud
model_profile
runtime_profile
agent_version           # nullable for cloud
protocol_version
started_at
first_delta_at
completed_at
first_token_latency
total_latency
completion_status
fallback_reason
fallback_consent
trace_id
```

---

# 28. Privacy Contract

V1 does not claim fully local/private document processing. Canonical documents and retrieval context are cloud-managed. Truthful product wording: **Optional local inference on your own device.**

---

# 29. Security Contract

All device-cloud traffic uses authenticated encrypted transport. Device credentials are least-privilege and grant no DB/admin/other-user access. No inbound ports or router configuration are required. Runtime/model/update artifacts must be approved and integrity-verified.

---

# 30. Logging and Sensitive Data

Logs should avoid raw prompt/context content by default and prefer identifiers, states, timings, provider/profile metadata, typed errors, and payload sizes. Sensitive debug payload logging must be explicit and non-default.

---

# 31. End-User Runtime UX Contract

The product works without ZKD Compute. Local compute is optional. Normal onboarding:

```text
Enable Local Compute
      ↓
Install ZKD Compute if missing
      ↓
Capability check
      ↓
Runtime compatibility
      ↓
Model download
      ↓
Integrity verification
      ↓
Benchmark
      ↓
READY
```

No terminal is part of normal onboarding.

---

# 32. User Transparency Contract

ZKD Compute exposes installed agent/runtime/model versions, model storage, backend, network behavior, inbound ports, and autostart state. Users can pause compute, disable local GPU, remove models, revoke device, and uninstall the app.

---

# 33. Benchmark Contract

Benchmarking may measure model-load latency, first-token latency, generation throughput, peak memory, and stability. Exact recommendation thresholds are not frozen.

---

# 34. Resource Policy Contract

V1 does not promise a precise GPU percentage cap. User policies may include GPU enablement, CPU fallback, minimum free VRAM, unload-when-idle, pause-while-busy, battery policy, OS autostart, and model-storage quota.

---

# 35. Device Messaging Abstraction

Cloud orchestration depends on a logical `DeviceTransport`, not directly on an in-process WebSocket dictionary. Logical operations include send job, cancel job, read state, and disconnect device. This allows later connection gateways/brokers without changing the agent protocol.

---

# 36. Connection Scaling Contract

V1 may start with a small ASGI deployment, but architecture must permit:

```text
API / Router
      │
      ▼
Device Messaging Abstraction
      │
      ▼
Connection Gateway(s)
      │
      ▼
Devices
```

Durable job state must not live only in one process's memory.

---

# 37. Backpressure

Cloud must not dispatch unlimited concurrent jobs to a device. Router/device expose queue depth, active jobs, and state. V1 may use one-generation-at-a-time per device. Exact limits are not frozen.

---

# 38. Job Deadline and Lease Semantics

Every attempt has bounded lifetime. Cloud remains authoritative for job state. Expired/terminal attempts cannot be resurrected by late events.

---

# 39. Terminal State Immutability

Once an attempt is `COMPLETED`, `FAILED`, `CANCELLED`, or `EXPIRED`, stale/duplicate late events cannot change it to another terminal state.

---

# 40. Protocol Compatibility

Handshake compares agent protocol version with cloud supported min/max. Incompatible agents receive `INCOMPATIBLE_PROTOCOL` and no generation jobs until upgraded.

---

# 41. Signed Update Contract

Agent/runtime updates must be integrity-protected. Unsigned/unverified updates are not silently installed. Job payloads can never supply arbitrary executable URLs.

---

# 42. Existing Legal RAG Blocks Remain Semantically Frozen

```text
BLOCK 1  Ingestion
BLOCK 2  Legal-aware token-safe chunking
BLOCK 3  Embedding + indexing
BLOCK 4  Hybrid retrieval
BLOCK 5  Deterministic context
BLOCK 6  Grounded generation/citation

NEW
BLOCK 7  Hybrid Runtime Contract
BLOCK 8  Device Compute Protocol
BLOCK 9  Compute Routing & Fallback
BLOCK 10 Runtime / Model Distribution
```

Blocks 1–5 remain cloud-canonical in V1. Block 6 gains provider abstraction while preserving grounding/citation semantics.

---

# 43. Migration Sequence

**Phase A — Always-online Control Plane:** move frontend, API, auth, PostgreSQL+pgvector, object storage, durable jobs, E5, retrieval, and workers away from dependency on the personal PC.

**Phase B — Generation Provider Abstraction:** introduce `GenerationProvider`, `LocalDeviceProvider`, and `CloudGenerationProvider`.

**Phase C — ZKD Compute Agent:** implement pairing, identity, heartbeat, capability reporting, runtime/model manager, benchmark, worker, secure client.

**Phase D — Personal Device Routing:** enable User A → Device A with ownership enforcement.

**Phase E — Cloud Fallback:** implement consent-aware `PREFER_LOCAL`.

**Phase F — Public Installer/Updater UX:** no terminal, no Docker, signed installer/updates, transparent installed-components UI.

**Phase G — Future Local Workloads:** separately evaluate OCR, rerank, vision, embedding after reproducibility/security proof.

---

# 44. Explicit Non-Goals for V1

- distributed GPU marketplace;
- cross-user compute;
- arbitrary remote execution;
- fully local/private canonical document mode;
- local legal chunking;
- local canonical vector indexing;
- automatic system driver installation;
- provider mixing within one answer;
- transport/vendor lock-in;
- large-scale multi-region gateway engineering before needed.

---

# 45. Acceptance Test Matrix

## Identity/ownership
- User A cannot dispatch to User B's device.
- Revoked device credential cannot reconnect.
- Stale connection cannot overwrite newer connection state.

## Device lifecycle
- `ONLINE` does not imply `READY`.
- Resource pressure causes `READY → UNAVAILABLE`.
- `DRAINING` rejects new jobs.
- Successful completion restores `READY`.

## Capability admission
- insufficient VRAM rejects before generation;
- busy GPU rejects/delays according to policy;
- missing model/profile prevents dispatch;
- incompatible protocol prevents dispatch.

## Reconnection storm
Simulate fleet disconnect and verify exponential backoff, jitter, backoff reset after stable reconnect, and control-plane responsiveness.

## Duplicate command delivery
Deliver the same `RUN_GENERATION` attempt twice; verify exactly one generation executes and terminal/provenance state is not duplicated.

## Stale connection epoch
Reconnect while old session emits events; old epoch events must be ignored/rejected.

## Payload limits
- 127 KiB request: accepted if otherwise valid.
- 129 KiB request: rejected before transport dispatch.
- no silent truncation.

## Zombie generation
Simulate `JOB_ACCEPTED → GENERATION_STARTED → silence`; watchdog must fail the attempt with `DEVICE_TIMEOUT` and terminate browser stream.

## Failure before first delta
With consent, a new cloud attempt may start. Without consent, cloud must not be called.

## Failure after first delta
Stream stops; cloud continuation is forbidden; Regenerate with Cloud creates a new generation run.

## Cancellation
Browser Stop propagates to device/provider; inference stops, deltas stop, resources release, state becomes `CANCELLED`.

## Consent
`NONE` never silently uses cloud; `ONE_TIME` applies once; `PERSISTENT` is auditable and revocable.

## Agent restart
Restart during an active job; reconnect with a new epoch; no zombie or duplicate generation results.

## Cloud process restart
Durable job state survives; terminal states are not lost; canonical state remains consistent.

---

# 46. Operational Metrics

Recommended metrics include:

```text
devices_online
devices_ready
devices_busy
reconnect_rate
authentication_failures
local_jobs_started
local_jobs_completed
local_jobs_failed
device_timeout_rate
job_rejection_rate
local_first_token_latency
cloud_first_token_latency
local_generation_latency
cloud_generation_latency
cloud_fallback_count
cloud_fallback_rate
fallback_reason_distribution
payload_too_large_count
duplicate_message_count
stale_epoch_event_count
cancel_success_rate
```

Monitoring vendor is not frozen.

---

# 47. Failure Taxonomy

At minimum:

```text
AUTH_FAILED
DEVICE_OFFLINE
DEVICE_BUSY
DEVICE_DRAINING
DEVICE_TIMEOUT
INSUFFICIENT_VRAM
INSUFFICIENT_RAM
MODEL_NOT_READY
RUNTIME_UNHEALTHY
INCOMPATIBLE_PROFILE
INCOMPATIBLE_PROTOCOL
PAYLOAD_TOO_LARGE
USER_PAUSED
CANCELLED_BY_USER
CLOUD_PROVIDER_ERROR
LOCAL_RUNTIME_ERROR
TRANSPORT_DISCONNECTED
DEADLINE_EXCEEDED
```

Errors are machine-readable internally and user-friendly externally.

---

# 48. Frozen vs Not Frozen

## Frozen

- cloud owns canonical truth;
- personal-device-only compute;
- generation-only local workload V1;
- explicit fallback consent;
- no mixed-provider answer;
- device lifecycle semantics;
- static + dynamic capability;
- job-time admission;
- common protocol envelope;
- job/attempt idempotency;
- connection epochs;
- ordered deltas;
- exponential backoff + jitter;
- application-level payload limits;
- generation watchdogs;
- typed failures;
- cancellation;
- provenance;
- no arbitrary remote execution;
- no developer-tool requirement for end users.

## Not frozen

- exact cloud/VPS provider;
- exact managed PostgreSQL provider;
- exact object-store vendor;
- exact cloud LLM provider;
- exact desktop framework;
- exact local inference runtime;
- exact local model;
- WebSocket vs another transport;
- Redis vs NATS vs another broker;
- exact heartbeat period;
- exact watchdog timeout values;
- exact benchmark thresholds;
- exact GPU eligibility threshold;
- exact reconnect delay constants;
- exact UI copy.

---

# 49. Definition of Done

Implementation is conformant only when:

```text
1. Website remains usable with every local device offline.
2. User can pair their device without terminal/Docker.
3. Readiness uses runtime + dynamic resources, not hardware name alone.
4. Duplicate/reconnected messages cannot execute duplicate generations.
5. Fleet reconnect uses backoff + jitter.
6. Oversized payloads fail before dispatch.
7. Zombie jobs terminate by watchdog.
8. Browser Stop reaches active provider.
9. Local failure after first delta never splices cloud output.
10. Cloud fallback never violates consent.
11. User A cannot use User B's device.
12. Cloud retains canonical data/security authority.
13. Every generation records provider/runtime provenance.
14. Agent cannot execute arbitrary remote commands.
15. End users never need Docker, Python, or terminal commands.
```

---

# 50. Final Contract Statement

> `rag.zkd.id.vn` is an always-online cloud-first multi-user Legal RAG product. The cloud owns canonical state, security, retrieval, orchestration, and availability. Each user may optionally install ZKD Compute to use the CPU/GPU of their own device as a personal generation accelerator. Local compute is optional and untrusted. Generation is the only client-offloaded workload in V1. Cloud fallback is consent-aware. Local and cloud outputs are never spliced into one generation. Reconnects use exponential backoff with jitter. Protocol payloads have explicit application-level limits. Every generation attempt has watchdogs preventing zombie jobs. The device protocol is idempotent, versioned, reconnect-safe, and independent from transport/vendor choices. End users never need Docker, terminal commands, or developer tooling.

```text
HYBRID_RUNTIME_CONTRACT_V1
STATUS: FROZEN
```

Implementation must preserve these invariants unless a deliberate V2 contract supersedes them.
