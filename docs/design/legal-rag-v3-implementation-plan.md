# Legal-RAG-V3 Future Implementation Plan

Status: **READY AS A PLAN — NOT AUTHORIZED OR EXECUTED**

This sequence implements only the approved prompt-version amendment. It must not absorb Context Selection V2, P1, retrieval tuning, parser work, model changes, or new infrastructure.

## Phase 01 — Baseline and frozen hashes

- Verify Evaluation V1/V2 hashes, immutable V2 prompt hash, and canonical V3 design hash.
- Capture production file fingerprints, schema/table count, and current `legal-rag-v2` selection.
- Run the full backend, frontend, and production-build baseline.
- Stop on any mismatch or failure.

## Phase 02 — Add immutable V3 prompt

- Copy `docs/design/legal-rag-v3-prompt.txt` byte-for-byte to `app/prompts/legal-rag-v3.txt`.
- Do not modify or overwrite V1/V2.
- Confirm UTF-8/LF/final-LF serialization and exact hash.

## Phase 03 — Prompt hash and version tests

- Add immutable hash assertions for V2 and V3.
- Assert canonical and runtime V3 bytes are identical.
- Assert unknown versions fail with existing `GENERATION_PROFILE_INVALID` semantics.

## Phase 04 — Server-side GenerationProfile selection

- Add `legal-rag-v3` to the existing `GenerationProfile.validate` and prompt-loader allowlists.
- Keep the dataclass fields, ownership, provider/model/settings, and request schemas unchanged.
- Initially keep the deployment/default selection on `legal-rag-v2` until activation approval.

## Phase 05 — Prompt-contract unit tests

- Test exactly-one marker instructions and authorized marker spellings.
- Test exact citation examples/invalid forms, two few-shots, anti-leakage, no P1 tokens, and no visible-reasoning request.
- Test no request-level prompt override in API/debug schemas.

## Phase 06 — Parser and streaming compatibility

- Run all existing answerability/citation tests unchanged.
- Verify marker stripping, insufficient short-circuit, public standardized message, SSE buffering, client disconnect, upstream cleanup, and provider error behavior.
- Do not change parsers to pass tests.

## Phase 07 — Targeted repeated real runs

- Run the four named historical cases at least five times each with real P0 contexts and provider settings.
- Expect bank and cross-document cases to retain the measured improvement/stability.
- Record `v2_civil_scope` without special prompt tuning; it may remain unresolved.

## Phase 08 — Full V2 answerable evaluation

- Run all 55 frozen answerable cases once with the real pipeline.
- Report acceptance, false abstention, citation metrics, expected-source match, status validity, and per-case failures.

## Phase 09 — Repeated V2 safety evaluation

- Run all 10 frozen unanswerable cases at least three times each.
- Require 30/30 abstentions, zero unsupported direct answers, and 100% exact-marker validity.

## Phase 10 — Category breakdown

- Separately report single evidence, multi evidence, hierarchy recovered, multi-document, and partial/qualified cases.
- Create human-review packages for unexpected-source and qualified-answer prose.

## Phase 11 — Token and latency comparison

- Reproduce the actual Qwen chat-template measurement and confirm the V3 runtime hash.
- Compare V2/V3 prompt tokens, TTFT, generation, and total latency with run-order caveats.
- Do not create an SLA or change generation settings.

## Phase 12 — Debug visibility

- Verify existing DebugTrace and SSE start metadata show `prompt_version=legal-rag-v3` under the test selection.
- Keep prompt choice read-only and never expose the full system prompt.
- Prefer hash evidence/tests over an internal schema addition; add only a hash-only startup diagnostic if separately justified.

## Phase 13 — Restart and rollback rehearsal

- Recreate API with V3 selection, verify health and a controlled smoke flow.
- Select V2 again, recreate API, verify V2 version/hash and behavior.
- Do not restart data services or delete volumes.

## Phase 14 — Full regression

- Run all backend tests, frontend tests, and the production frontend build.
- Record exact collected/passed/failed/warnings/duration.
- Require zero failures and no schema drift.

## Phase 15 — Re-freeze decision

- Present the complete before/after report and human-review packages.
- Activate V3 only after explicit approval and every mandatory criterion passes.
- Re-freeze Block 6 with only the prompt-version amendment; keep V2 as immediate rollback.

## Explicit exclusions

- No Block 1–5 changes.
- No P1 structural presentation.
- No Context Selection V2 or `v2_civil_scope` special rule.
- No retrieval, hierarchy, Top-K, RRF, or budget change.
- No model/provider/tokenizer/generation-parameter change.
- No second LLM, classifier, judge, score threshold, retry, or background job.
- No parser, API, SSE, provenance, or schema change.
- No user/debug prompt-version mutation.

## Definition of implementation-ready

The plan is implementation-ready when a reviewer accepts the exact prompt/hash, semantic diff, validation gates, and rollback procedure. “Ready” authorizes a future controlled implementation task only; it does not authorize production activation.
