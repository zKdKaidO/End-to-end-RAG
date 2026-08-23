# Legal-RAG-V3 Design Verification

Date: 2026-08-22 (Asia/Saigon)

Status: **PASS — DESIGN ONLY, NOT ACTIVE**

## Frozen inputs

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Production V2 prompt SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- Proposed V3 design prompt SHA-256: `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf`

All frozen hashes matched before and after design work.

## Baseline backend regression

```text
docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests -v
```

- collected: 235
- passed: 235
- failed: 0
- warnings: 8
- duration: 89.01 seconds

## Prompt artifact verification

- Canonical serialization: UTF-8, LF, one trailing LF
- Bytes: 1,441
- Prompt embedded in contract equals canonical bytes/text: PASS
- V2 case-ID matches in prompt: 0
- Forbidden P1/hierarchy or benchmark-specific terms checked: 0
- Required design artifacts present: 7/7, including canonical prompt text
- `app/prompts/legal-rag-v3.txt` exists: NO
- Production `GenerationProfile` changed: NO
- Runtime prompt allowlists changed: NO
- Production default remains `legal-rag-v2`: YES

## Real tokenizer/chat-template measurement

The current Qwen tokenizer, chat template, `PromptTokenCounter`, `thinking=false`, P0, and all 65 frozen V2 contexts were used.

| Prompt | Mean | Min | Max |
|---|---:|---:|---:|
| Production V2 | 2,860.38 | 1,304 | 4,508 |
| Winning experimental prompt | 2,795.38 | 1,239 | 4,443 |
| Proposed V3 design | 2,836.38 | 1,280 | 4,484 |

Proposed V3 minus V2: -24 tokens on every measured context. Proposed V3 minus the exact winner: +41 tokens, attributable to the explicit qualified-answer and no-visible-analysis clauses required by the design contract.

## Final regression

Backend:

- collected: 235
- passed: 235
- failed: 0
- warnings: 8
- duration: 88.71 seconds

The pytest process printed its complete successful terminal summary. The host-side Compose wrapper retained an inherited pipe afterward and was stopped only after pytest had completed; the recorded pytest summary is authoritative.

Frontend:

- test files: 5 passed
- tests: 11 passed
- failed: 0
- duration: 938 ms

Production build:

- TypeScript/Vite: PASS
- transformed modules: 30
- Vite build duration: 118 ms

## Architecture audit

- Blocks 1–5: unchanged
- Block 6 production behavior: unchanged
- P1: not included
- Provider/model/tokenizer/profile: unchanged
- Parsers/streaming/API/provenance: unchanged
- Database/schema: unchanged
- Tracked production diffs: 0
- Production activation: NO
