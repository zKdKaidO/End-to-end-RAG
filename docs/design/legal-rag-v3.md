# Legal-RAG-V3 Design

Status: **DESIGN READY FOR HUMAN REVIEW — NOT IMPLEMENTED OR ACTIVE**

Design date: 2026-08-22 (Asia/Saigon)

## Decision

Legal-RAG-V3 is a prompt-only, versioned Block 6 amendment derived from the winning `legal-rag-v3-compact-fewshot-experimental` + P0 experiment. P0 is the existing Block 5 prompt-facing evidence presentation. P1 anchor/child presentation is explicitly excluded.

The proposed production identifier is `legal-rag-v3`. The canonical design serialization is [legal-rag-v3-prompt.txt](legal-rag-v3-prompt.txt), encoded as UTF-8, LF line endings, with one final LF. Its SHA-256 is:

```text
35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf
```

This task does not place the prompt in `app/prompts`, add V3 to runtime allowlists, change `GENERATION_PROMPT_VERSION`, or activate it. Production remains `legal-rag-v2` with SHA-256 `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`.

## Measured basis

The final ablation used the real `qwen3.5:9b` provider path, production-equivalent generation settings, the real Qwen tokenizer/chat template, identical selected contexts, and all frozen V2 cases.

| Metric | Production V2 | Winning compact few-shot + P0 |
|---|---:|---:|
| Answerable acceptance | 87.27% | 94.55% |
| False abstention | 12.73% | 5.45% |
| Citation structural validity | 87.27% | 94.55% |
| Expected-source match | 85.45% | 90.91% |
| Status validity | 100% | 100% |
| Repeated unanswerable abstention | 10/10 baseline | 60/60 A/B safety calls |
| Unsupported direct answers | 0 | 0 |

P1 accepted 51/55 answerable cases versus P0's 52/55 and produced no net full-corpus grounded gain. It would require a Block 5 presentation-contract amendment. The smallest defensible design is therefore prompt-only V3 with P0.

The exact design serialization adds the explicitly requested qualified-answer language and no-visible-reasoning rule to the compact winner. It has not itself been activated or rerun for generation quality. The winning metrics are implementation parity references, not results claimed for the design file.

## Goals and non-goals

V3 should answer when the supplied evidence is sufficient, including when support is distributed across sources or supports a narrower qualified conclusion. It must continue to abstain when evidence is merely topical, materially incomplete, assumption-dependent, or reliant on external legal knowledge.

V3 is not intended to maximize answer frequency. It introduces no score threshold, answerability classifier, second LLM, judge, retry, parser relaxation, retrieval change, context change, or case-specific instruction.

## Frozen architecture

The following remain unchanged:

- Blocks 1–5, including hybrid/hierarchy retrieval and Block 5 ordering, formatting, and budget;
- P0 evidence wrappers and source IDs;
- provider `ollama` and model `qwen3.5:9b`;
- Hugging Face tokenizer `Qwen/Qwen3.5-9B` and its chat template;
- model context limit 32,768, Block 5 context budget 4,096, max output 512, and prompt safety margin 32;
- thinking `false`, temperature 0.0, top-p 0.9, top-k 20, and request timeout 180 seconds;
- answerability and citation parsers;
- public `COMPLETED`, `COMPLETED_WITH_WARNINGS`, and `INSUFFICIENT_EVIDENCE` semantics;
- citation/provenance mapping;
- non-stream and SSE `start` / `delta*` / `done|error` contracts;
- API schemas and database schema.

The future implementation changes only the immutable system-prompt artifact, adds its identifier to existing server-side validation/loading allowlists, and later selects it through the existing server-owned `GenerationProfile` setting after approval.

V3 introduces no error category or recovery path. Existing prompt assembly/counting, hard-budget guard, provider request, status parsing, citation parsing/validation, provenance mapping, streaming cleanup, and internal-error semantics remain authoritative. There is no V3-specific retry or fallback generation.

## No P1 contract

The model-facing evidence remains the current P0 format. V3 does not receive or require:

- `candidate_origin`;
- `HIERARCHY_CHILD` or `DIRECT_CHILD` labels;
- anchor/child relationships;
- hierarchy mechanics;
- evaluation labels or expected evidence.

Hierarchy retrieval can still improve the selected context, but that internal origin is not exposed to the model.

## Versioning and ownership

| Concern | Design contract |
|---|---|
| Identifier | `legal-rag-v3` |
| Design source | `docs/design/legal-rag-v3-prompt.txt` |
| Future runtime file | `app/prompts/legal-rag-v3.txt`, byte-identical to the design source |
| Historical prompt | `app/prompts/legal-rag-v2.txt` remains immutable |
| Selection owner | Server-owned `GENERATION_PROMPT_VERSION` loaded into `GenerationProfile` |
| Client control | None; normal and debug requests cannot override prompt version |
| Loader | Existing `load_system_prompt`, with `legal-rag-v3` added to its allowlist only during implementation |
| Audit | Exact SHA test plus `prompt_version` in existing GenerationResult/DebugTrace/SSE start metadata |
| Rollback | Select `legal-rag-v2` and recreate/restart the API process; no data operation |

Prompt hash need not be added to the public or debug schema for initial V3. The exact hash is enforced by tests and recorded in release evidence. An internal startup log field may include it later if that requires no public contract change; the full prompt must never be logged.

## Remaining known limitation

`v2_civil_scope` remained ungrounded in 0/5 targeted runs for both finalists and also failed their full-evaluation runs. No special wording, vocabulary, document hint, or case pattern is added. It is classified as an out-of-scope future Context Selection V2 candidate and does not invalidate V3 if aggregate and safety gates otherwise pass.

## Design acceptance

This design is ready for human review because it is exact, versioned, hashable, compact, rollback-safe, benchmark-generic, and bounded to the measured prompt-only change. Production activation remains a separate, explicitly approved implementation phase governed by [legal-rag-v3-validation-plan.md](legal-rag-v3-validation-plan.md).
