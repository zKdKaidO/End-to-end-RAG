# Security Threat Model V1

## Scope and invariants

This assessment covers the local Vietnamese Legal RAG product boundary: browser, FastAPI, authentication sessions, PostgreSQL, Redis/RQ, MinIO, PDF workers, retrieval/context/generation, and the local Ollama provider. Tests used only controlled local users, documents, and synthetic canaries.

The protected assets are private source documents, extracted text and embeddings, chat history, account/session material, generation capacity, worker availability, provider access, and application secrets. Trust boundaries are browser-to-API, API-to-data services, API-to-provider, API-to-RQ, RQ-to-workers, and PDF bytes-to-parser.

Core RAG semantics remain frozen. Production remains `qwen3.5:9b` with `legal-rag-v2`. Authorization is derived from document grants and the Global corpus predicate; legacy `documents.user_id` is not an authorization source.

## Threat actors

- Anonymous remote client: credential attacks, oversized requests, malicious uploads, error discovery.
- Authenticated user: IDOR, explicit UUID injection, cross-user retrieval, generation exhaustion, stored prompt injection.
- Malicious document supplier: malformed/compressed PDFs, parser network references, evidence-layer prompt injection.
- Adjacent network client: direct PostgreSQL, Redis/RQ, MinIO, or Ollama access.
- Accidental operator/developer disclosure: committed secrets, verbose errors, unsafe service binding.

## Red-team findings

| Severity | Reproduced pre-hardening weakness | Security impact | Resolution |
|---|---|---|---|
| High | No distributed login throttling | Online password guessing | Redis dual token bucket |
| High | No cross-session/user/global inference admission | Provider exhaustion | Redis rate and lease admission |
| High | PostgreSQL, Redis, MinIO and Ollama bound beyond the trusted local boundary | Data/job/provider bypass | Internal Docker network and loopback Ollama |
| High | A tracked local `.env` and fallback development credentials | Secret disclosure/reuse | Rotation, untracking, ignore rules, required env values |
| Medium | PDF validation accepted magic bytes only and buffered the full upload | Parser and memory abuse | Bounded stream, structural validation and caps |
| Medium | Workers had no memory/CPU/PID/job-time containment | Blast-radius expansion | Container limits and job timeouts |
| Medium | Raw worker exception text could enter user-visible responses | Internal detail disclosure | Central public error sanitization |
| Medium | API/frontend lacked deliberate security headers and global request limits | Browser/input hardening gaps | CSP/header middleware and bounded inputs |

No post-remediation Blocker or High path remained in the tested local capability surface.

## Controls verified as already effective

Opaque session tokens are hash-only at rest; cookies are HttpOnly/SameSite and Secure is deployment-configured. Session expiry, revocation, password-change revocation, disabled/deleting account rejection, uniform authentication failure, trusted-origin mutation checks, credentialed CORS allowlisting, 404-uniform IDOR handling, grant-filtered dense/lexical retrieval, private MinIO policy, evidence delimiters/prompt-injection rules, and account-deletion shared-data preservation were already effective.

## Residual risks

Redis uses network isolation rather than Redis AUTH/mTLS. Local HSTS is disabled because the development endpoint is HTTP; HTTPS deployments must enable it at the edge. PDF engines remain complex native-code attack surfaces despite validation and container limits. Prompt-injection resistance is empirical, not a proof of legal correctness. Worker egress isolation requires model caches to be pre-seeded. Reverse-proxy deployments must define a trusted client-IP topology before using forwarded addresses for network-rate dimensions.
