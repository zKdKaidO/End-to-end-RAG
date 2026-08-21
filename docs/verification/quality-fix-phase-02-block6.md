# Quality Fix Phase 02 — Block 6 Answerability and Prompt V2

Date: 2026-08-19

## Approved contract amendment

- Added the authoritative first-output markers `[STATUS: ANSWERABLE]` and `[STATUS: INSUFFICIENT_EVIDENCE]`.
- Added a deterministic parser. It accepts only the documented marker grammar and never infers status from natural-language phrases.
- Missing, malformed, duplicate, and unknown markers produce explicit machine diagnostics and fail safely as `COMPLETED_WITH_WARNINGS`; they are not guessed to mean insufficient evidence.
- The marker is stripped before citation parsing and never appears in public `answer_text`.
- An authoritative insufficient marker maps to HTTP 200 / `INSUFFICIENT_EVIDENCE`, a standardized public message, and empty citation lists. No retry or second LLM call is made.
- Streaming retains `start`, `delta*`, `done` / `error`, buffers the initial marker, strips it from deltas, and closes the provider stream after an authoritative insufficient decision.

## Prompt version

- `legal-rag-v1` remains unchanged.
- `legal-rag-v2` is the production profile.
- V2 reinforces exact `[S1]` citation syntax and explicitly rejects `[Evidence S1]`, `Evidence S1`, `(S1)`, and `Source S1`.
- V2 contains one concise valid-citation example and one concise topical-but-insufficient abstention example.

## Token-budget evidence

- V1 system prompt: 1,630 tokens
- V2 system prompt: 1,823 tokens
- Overhead: 193 tokens
- Measured guarded total: 2,367 / 32,768 tokens
- Prompt Budget Guard: PASS
- Shared production tokenizer instance: PASS

## Tests

Deterministic tests cover valid markers, whitespace, missing/malformed/unknown/duplicate status, public stripping, SSE stripping, insufficient mapping, citation preservation, invalid near-miss syntax, client disconnect, provider errors, and prompt budget behavior.

Result: PASS.
