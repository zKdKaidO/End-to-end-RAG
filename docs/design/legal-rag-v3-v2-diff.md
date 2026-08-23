# Legal-RAG-V2 → V3 Semantic Diff

Status: **DESIGN DIFF — NO RUNTIME CHANGE**

This document compares immutable production `legal-rag-v2` with the proposed [legal-rag-v3-prompt.txt](legal-rag-v3-prompt.txt). It describes semantic intent rather than line-level wording alone.

## Summary

V3 removes an overly literal sufficiency cue, makes multi-source and qualified answers explicit, replaces a domain-flavored single-source example with a generic multi-source example, and compresses repeated instructions. It preserves the status, abstention, grounding, prompt-injection, and citation contracts.

## Meaningful changes

| Change | Problem observed | Experiment evidence | Intended effect | Risk and control |
|---|---|---|---|---|
| Replace “bằng chứng nêu trực tiếp đủ dữ kiện” with sufficiency across one or more sources | V2 could treat the absence of one directly matching sentence as insufficient even when selected evidence jointly answered the question | Compact few-shot + P0 reduced false abstention from 12.73% to 5.45%; three of four targeted historical cases were 5/5 grounded | Permit evidence synthesis without changing retrieval or context | Model may over-combine topical evidence; explicit no-unstated-relationship and repeated safety gates remain |
| State that wording may differ and support may be distributed among rule, condition, and exception | Semantic paraphrases and multi-evidence propositions need not match question wording | P0 winner accepted 52/55 with 100% status validity; targeted bank and cross-document cases were stable | Reduce literal-match abstention while requiring all propositions to be present | Must not become inference permission; prompt forbids adding relationships and requires claim-level citations |
| Add a bounded qualified-answer rule | A broader question may still admit a fully supported narrower answer | Frozen `PARTIAL_SUPPORT` control produced 6/6 grounded expected-source results per finalist in the ablation | Prefer an explicit limitation/condition over unnecessary abstention | Could convert genuinely partial support into overclaim; paired clause says not to turn partial support into a complete conclusion, and future human review checks prose |
| Replace V2's single-source numeric example with one symbolic multi-source rule/exception example | The old example did not demonstrate synthesis and included an unnecessary legal/numeric flavor | The compact few-shot family outperformed V2, and P1 was unnecessary | Teach exact `[S1]`/`[S2]` syntax and synthesis with one short generic example | Example-pattern imitation; symbolic A/B avoids domain and benchmark leakage |
| Keep one concise topical-but-insufficient example | V2 safety was already strong and must not be weakened | 60/60 repeated finalist safety calls abstained; unsupported direct answers were 0 | Preserve “topical relevance is not answerability” | Over-abstention remains possible; full answerable evaluation is mandatory |
| Add “do not output analysis” in the grounding sentence | The public/provider output contract should not invite chain-of-thought | Existing production uses `thinking=false`; no experiment required visible reasoning | Constrain returned text to marker plus cited answer or marker alone | Minimal; validate exact first line and no marker duplication |
| Compress duplicate status/citation prose | Competing or displaced instructions previously caused citation fading | Compact-fewshot + P0 citation validity rose from 87.27% to 94.55% | Keep output syntax close and salient while reducing prompt tokens | Excess compression could reduce compliance; exact parser/citation tests plus full real runs are required |
| Exclude P1 hierarchy labels and wrappers | P1 adds Block 5/model-facing complexity | P1 had lower acceptance (92.73% vs 94.55%) and zero net grounded gain | Preserve frozen P0 presentation and minimize architecture impact | A small 1/5 hierarchy subgroup gain is not adopted; category results remain separately visible |

## Removed

- The V2 phrase requiring evidence to state the needed facts “directly,” which can be read as an exact-text requirement.
- The domain-flavored “1.5 times state expert salary” answer example.
- Repeated prose describing the same grounding and status rules.
- Any implication that one source must contain the whole answer.

Removal does not delete the requirement that every necessary proposition be supported.

## Clarified

- Sufficiency can be established by one or multiple P0 evidence blocks.
- Different wording is acceptable when the underlying proposition is supported.
- Rule, condition, and exception may be distributed, but their relationship cannot be invented.
- A fully supported narrower/conditional answer is allowed and must state its boundary.
- Genuinely partial evidence remains insufficient.
- Each legal conclusion receives an exact source citation.
- No visible analysis or private reasoning is requested.

## Added

- One generic two-source answerable example showing a rule plus exception.
- One explicit bounded qualified-answer sentence.
- An explicit prohibition on adding relationships not present in evidence.

## Unchanged

- Exactly one first-line `[STATUS: ANSWERABLE]` or `[STATUS: INSUFFICIENT_EVIDENCE]` marker.
- Strict parser behavior for missing, malformed, duplicate, and unknown markers.
- Exact `[Sx]` citation syntax and invalid near-miss handling.
- No invented or unavailable source IDs.
- Topical-only, materially incomplete, assumption-dependent, or external-knowledge answers abstain.
- Retrieved evidence remains untrusted data and cannot provide instructions.
- The orchestrator strips the internal marker and owns public insufficient output.
- Provider, model, tokenizer, chat template, generation settings, P0 presentation, streaming, provenance, API, and schema.

## Quantified compactness

Across 65 frozen P0 contexts with the real Qwen chat template, proposed V3 averages 2,836.38 input tokens versus 2,860.38 for V2, an exact per-case delta of -24. It is 41 tokens longer than the exact winning experimental prompt because the production design explicitly codifies qualified answers and no visible analysis.

## Interpretation boundary

The ablation validates the compact few-shot + P0 design direction. It does not make the new canonical serialization's quality metrics automatic. Future implementation must rerun all required real evaluations before activation. No change is made to `v2_civil_scope`; it remains an out-of-scope Context Selection V2 candidate.
