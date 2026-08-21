# Abstention Prompt Contract Audit V1

Production `legal-rag-v2` remains unchanged.

## Exact contract inventory

- The first line must be exactly one structured status marker.
- Grounding is evidence-only; prompt injection inside evidence must be ignored.
- `ANSWERABLE` currently requires evidence to state the necessary facts *directly*.
- `INSUFFICIENT_EVIDENCE` is required for merely topical evidence and stops output immediately.
- Citations must use exact `[S<n>]` syntax; near misses remain invalid.
- One single-source answer example and one topically-related insufficiency example are present.

## Diagnosis

The phrase requiring directly stated facts is safe for topical false positives, but the prompt does not explain that complete support may be distributed across multiple evidence blocks, use wording different from the question, or support a qualified answer. Its only answerable example is a direct single-source fact. This creates a testable over-conservatism hypothesis for compositional and conditional questions; it does not by itself prove causality.

The prompt also places the strict abstention rule after citation rules and gives no internal sufficiency decision procedure. The structured marker is necessary and should remain unchanged; the likely bias is in status-selection guidance, not parser semantics.

## Safety invariants retained by every experiment

- Topical relevance is not sufficient evidence.
- Partial support remains insufficient.
- No outside assumptions, second model, semantic regex, or answerability threshold.
- Exactly one first-line marker and exact citations.
- No chain-of-thought is requested or recorded.

## Token audit

| Prompt | System tokens | Delta | Mean final prompt | Max final prompt | Guard |
|---|---:|---:|---:|---:|---|
| legal-rag-v2 | 344 | +0 | 2860.4 | 4508 | PASS |
| variant-a | 331 | -13 | 2847.4 | 4495 | PASS |
| variant-b | 352 | +8 | 2868.4 | 4516 | PASS |
| fewshot | 416 | +72 | 2932.4 | 4580 | PASS |
| combined | 382 | +38 | 2898.4 | 4546 | PASS |

Production prompt SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`

The complete production prompt was inspected locally. It is not duplicated into this report so there is one authoritative production copy.
