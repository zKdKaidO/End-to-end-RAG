# Legal-RAG-V3 Validation Plan

Status: **FUTURE IMPLEMENTATION GATE — NOT EXECUTED BY THIS DESIGN PHASE**

## Frozen inputs

Before every implementation/evaluation run, verify:

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`;
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`;
- immutable V2 prompt SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`;
- canonical V3 prompt SHA-256: `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf`;
- unchanged Blocks 1–5 production fingerprints or reviewed diff;
- production-equivalent model/profile values.

Hash mismatch, baseline failure, or an unapproved Block 1–5 diff stops the implementation gate. Datasets are not rewritten to improve results.

## Reference measurements

Production V2 is the before baseline:

- answerable acceptance 87.27%;
- false abstention 12.73%;
- citation validity 87.27%;
- expected-source match 85.45%;
- unanswerable abstention 10/10;
- unsupported direct answers 0;
- status validity 100%.

The winning compact-fewshot + P0 experiment is a parity reference, not a generic SLA:

- answerable acceptance approximately 94.55%;
- false abstention approximately 5.45%;
- citation validity approximately 94.55%;
- expected-source match approximately 90.91%;
- unanswerable abstention 10/10;
- unsupported direct answers 0;
- status validity 100%.

No new score threshold is introduced. “Material improvement” and “material regression” require the measured before/after table and human approval; they are not converted into an arbitrary hidden cutoff.

## Static and unit validation

Tests must prove:

1. `legal-rag-v2.txt` remains byte-identical and its hash is unchanged.
2. `legal-rag-v3.txt` exists only after the implementation phase and matches the canonical design hash exactly.
3. Profile and prompt-loader allowlists recognize V1, V2, and V3 and reject unknown values.
4. Default/server deployment selection remains server-owned; request schemas contain no prompt override.
5. Normal Ask UI and API cannot mutate prompt version.
6. Debug trace displays the selected `prompt_version` but cannot change it.
7. The V3 prompt instructs exactly one first-line marker and contains only the two authorized marker values.
8. The answerable few-shot has one marker and only valid `[S1]`/`[S2]` citations.
9. The insufficient few-shot has one insufficient marker and no answer/citation continuation.
10. Invalid citation forms remain invalid; `[S1]` remains valid.
11. Examples contain no case IDs, frozen questions/answers, document-specific entities, chunk excerpts, or expected evidence.
12. V3 has no P1/candidate-origin/anchor-child formatting dependency.
13. Provider/model/tokenizer/generation values are unchanged.
14. Existing answerability and citation parser tests pass without modification or relaxation.
15. Non-stream and streaming marker stripping, insufficient suppression, disconnect cleanup, and provider-error paths remain green.
16. Actual Qwen `PromptTokenCounter` and chat-template counts fit the unchanged hard guard for every frozen case.
17. Switching the server-owned profile back to V2 loads the V2 hash and restores V2 selection.

## Targeted real repeatability

Use real Block 4, real frozen Block 5/P0, real Block 6, real Ollama `qwen3.5:9b`, and production-equivalent settings. Run at least five generations for each:

- `v2_bank_scope_ratios`: should remain grounded and stable;
- `v2_bank_below_80_measures`: should remain qualified/grounded and stable;
- `v2_cross_document_effective_dates`: should remain grounded and stable;
- `v2_civil_scope`: record honestly; it may remain unresolved and does not alone block V3 when safety and aggregate gates pass.

Record answerability status, exactly-one-marker validity, answer text, citations, invalid citations, expected-source match, provider usage, TTFT, generation latency, and total latency for every run.

## Full frozen V2 evaluation

Run all 55 answerable and all 10 unanswerable cases. Do not substitute mocks for final metrics. Report:

- answerable acceptance and false abstention;
- citation presence and structural validity;
- expected-source match;
- missing and invalid citation rates;
- status failures and duplicate markers;
- correct abstention and unsupported direct answers;
- retrieval/context/generation/total timings.

Any result using a structurally valid but unexpected source is placed in a side-by-side human-review package. Expected-source mismatch is not automatically equated with legal incorrectness, and no LLM judge is added.

## Repeated safety

Run all 10 frozen unanswerable cases at least three times each under V3: 30 minimum real calls. Acceptance requires:

- 30/30 structured abstentions;
- 0 unsupported direct answers;
- 100% valid, exactly-one first-line markers;
- no citation or answer continuation after insufficient status.

Prefer five repetitions for any case that shows instability or was historically risky. One safety failure rejects activation pending diagnosis; do not tune the dataset or add a score threshold.

## Partial-support and qualified answers

Run every frozen `PARTIAL_SUPPORT`/qualified-answer case and create a human-review package containing the question, selected P0 evidence, answer, citations, and exact excerpts. Verify structurally that citations are valid and expected sources are present. Human reviewers decide whether prose accurately states the supported limitation rather than converting partial evidence into a complete claim.

## Required category breakdown

Report separately, even though strata may overlap:

- single evidence;
- multi evidence;
- hierarchy recovered;
- multi-document;
- qualified/partial support;
- answerable versus hard-unanswerable versus out-of-corpus.

Multi-evidence grounding was 66.67% for both finalists and must not be hidden behind aggregate acceptance. Do not add a reranker, Top-K change, P1 formatting, or Context Selection V2 in this prompt implementation.

## Token and latency comparison

Use the real Qwen tokenizer/chat template and the same selected contexts. Report V2 versus V3 prompt tokens, TTFT, generation time, and total time, including run order and warm-up limitations. The design measurement is V3 -24 tokens per frozen case versus V2; implementation must reproduce the canonical hash and remeasure. Do not invent an SLA.

## Activation acceptance checklist

- [ ] Dataset hashes unchanged.
- [ ] Blocks 1–5 unchanged.
- [ ] V2 retained byte-for-byte.
- [ ] V3 runtime file equals canonical design hash.
- [ ] False abstention materially improves relative to V2 and is compared with the measured parity reference.
- [ ] Citation validity does not regress.
- [ ] Expected-source performance does not materially regress; alternatives receive human review.
- [ ] Status validity is 100%; duplicate/malformed markers are zero.
- [ ] Repeated unanswerable safety is perfect on frozen controls.
- [ ] Unsupported direct answers remain zero.
- [ ] No second LLM, classifier, judge, parser relaxation, P1, or Block 5 change.
- [ ] Full backend/frontend/build regression has zero failures.
- [ ] Restart and rollback tests pass.

## Blind holdout

Evaluation V2 remains a strong regression set but is no longer a clean unseen holdout because it drove failure discovery, prompt calibration, ablation, and winner selection.

A future **Legal Evaluation V3 Holdout** is required before a broad production-readiness claim. Do not create it in the prompt implementation task. Initially target approximately 20–30 high-quality cases from newly approved legal source material not used in V3 design. Include answerable, unanswerable, multi-evidence, qualified-answer, document-ambiguity, and cross-document questions. Freeze and hash it before first use.
